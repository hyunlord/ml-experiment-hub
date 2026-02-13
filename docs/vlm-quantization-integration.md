# vlm_quantization Integration Guide

ml-experiment-hub와 vlm_quantization 프로젝트를 연동하여 학습을 관리하고 실시간 모니터링하는 가이드.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  ml-experiment-hub (port 8000)                              │
│                                                             │
│  ┌─────────────┐   ┌──────────────┐   ┌──────────────────┐  │
│  │ Experiment   │   │ Compat       │   │ WebSocket        │  │
│  │ API          │   │ Bridge       │   │ Streaming        │  │
│  │              │   │              │   │                  │  │
│  │ POST /api/   │   │ POST /api/   │   │ WS /ws/runs/     │  │
│  │  experiments │   │  metrics/    │   │  {id}/metrics    │  │
│  │ POST /api/   │   │  training    │   │ WS /ws/runs/     │  │
│  │  runs/{id}/  │   │ POST /api/   │   │  {id}/system     │  │
│  │  metrics     │   │  metrics/    │   │ WS /ws/runs/     │  │
│  │              │   │  eval        │   │  {id}/logs       │  │
│  └──────┬───────┘   └──────┬───────┘   └──────┬───────────┘  │
│         │                  │                  │              │
│         └──────────┬───────┘                  │              │
│                    ▼                          │              │
│             ┌──────────┐                      │              │
│             │ SQLite/  │◄─────────────────────┘              │
│             │ Postgres │                                     │
│             └──────────┘                                     │
└─────────────────────────────────────────────────────────────┘
        ▲                           ▲
        │ HTTP POST                 │ WebSocket
        │ (MonitorCallback)         │ (Dashboard)
        │                           │
┌───────┴───────┐           ┌───────┴───────┐
│ vlm_quanti-   │           │ Frontend      │
│ zation        │           │ (port 5173)   │
│ train.py      │           │ RunMonitor    │
│ + Monitor     │           │ Compare       │
│   Callback    │           │ Dashboard     │
└───────────────┘           └───────────────┘
```

## 1. Prerequisites

### vlm_quantization train.py 1-line 패치

MonitorCallback이 hub의 run_id를 사용하도록 train.py에 1줄을 수정합니다.

```diff
# vlm_quantization/train.py (line ~97)
- run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
+ run_id = monitor_cfg.get("run_id", datetime.now().strftime("%Y%m%d_%H%M%S"))
```

이 패치로 hub가 YAML config에 `monitor.run_id`를 주입하면 MonitorCallback이 hub의 정수 run_id를 사용합니다.
패치 없이도 동작하지만, bridge가 "가장 최근 실행중인 run"으로 fallback하므로 동시 실행 시 충돌 가능성이 있습니다.

### 환경 설정

```bash
# 1. ml-experiment-hub 설정
cd ml-experiment-hub
cp .env.example .env

# .env에서 PROJECTS_DIR을 vlm_quantization 경로로 설정
# PROJECTS_DIR=/path/to/parent/of/vlm_quantization
```

`.env` 예시:
```env
DATABASE_URL=sqlite+aiosqlite:///./ml_experiments.db
PROJECTS_DIR=/Users/rexxa/github
CHECKPOINT_BASE_DIR=/Users/rexxa/github/vlm_quantization/checkpoints
LOG_DIR=./logs
CORS_ORIGINS=["http://localhost:5173"]
```

### 초기 셋업

```bash
# ml-experiment-hub 의존성 설치 + DB 마이그레이션 + 스키마 시딩
./scripts/setup.sh

# 개발 서버 시작 (backend :8000 + frontend :5173)
./scripts/dev.sh
```

## 2. PyTorchLightningAdapter 동작 방식

hub가 실험을 시작할 때 내부적으로 수행하는 과정:

```python
# 1. 사용자가 UI에서 flat config를 저장
flat_config = {
    "model.backbone": "google/siglip2-so400m-patch14-384",
    "model.freeze_backbone": True,
    "training.batch_size": "auto",
    "data.extra_datasets": ["coco_ko"],
    "monitor.enabled": True,
    "monitor.log_every_n_steps": 10,
}

# 2. ExperimentRun 생성 (DB에서 run_id=42 할당)
# 3. Adapter가 flat -> nested dict -> YAML 변환
#    + monitor.server_url, monitor.run_id 자동 주입
adapter = PyTorchLightningAdapter()
config = unflatten_dict(flat_config)
config = adapter.inject_monitor_config(config, run_id=42, server_url="http://localhost:8000")

# 4. YAML 파일 생성
yaml_content = adapter.config_to_yaml(config)
# 결과:
# model:
#   backbone: google/siglip2-so400m-patch14-384
#   freeze_backbone: true
# training:
#   batch_size: auto
# data:
#   extra_datasets:
#     - coco_ko
# monitor:
#   enabled: true
#   server_url: http://localhost:8000
#   run_id: "42"
#   log_every_n_steps: 10

# 5. subprocess로 학습 시작
# cmd: ["python", "train.py", "--config", "/tmp/exp_1_xxx.yaml"]
```

### Compatibility Bridge

MonitorCallback → Hub 엔드포인트 매핑:

| MonitorCallback 엔드포인트 | Hub Bridge 엔드포인트 | 설명 |
|---|---|---|
| `POST /api/training/status` | `backend/api/compat.py` | 학습 진행상태 (epoch, step, total) |
| `POST /api/metrics/training` | `backend/api/compat.py` | 학습 step 메트릭 (loss 등) |
| `POST /api/metrics/eval` | `backend/api/compat.py` | 검증 epoch 메트릭 (mAP, P@K 등) |
| `POST /api/metrics/hash_analysis` | `backend/api/compat.py` | 해시 분석 (bit activation 등) |
| `POST /api/checkpoints/register` | `backend/api/compat.py` | 체크포인트 등록 (ack only) |

Bridge가 자동으로:
1. MonitorCallback의 `run_id`를 hub의 정수 run_id로 변환
2. Named loss fields를 generic metrics dict로 변환
3. MetricLog에 저장 + WebSocket으로 실시간 broadcast

## 3. 테스트 시나리오

### Scenario A: 기본 학습 실행

#### Step 1: 스키마 선택

1. http://localhost:5173 접속
2. "New Experiment" 클릭
3. Schema 드롭다운에서 **"Cross-Modal Deep Hashing (SigLIP2)"** 선택
   - 시딩된 스키마가 자동으로 폼 필드를 생성합니다

#### Step 2: Config 설정

다음 값으로 설정:

| 필드 | 값 | 설명 |
|---|---|---|
| Freeze Backbone | `true` (체크) | 백본 고정, 해시 헤드만 학습 |
| Batch Size | `auto` | GPU VRAM에 따라 자동 결정 |
| Extra Datasets | `coco_ko` (선택) | 한국어 COCO 캡션 추가 |
| Max Epochs | `15` | Colab preset과 동일 |
| Monitor Enabled | `true` (체크) | 실시간 모니터링 활성화 |

또는 Preset 드롭다운에서 **"Colab (T4/A100)"** 선택하면 자동으로 채워집니다.

#### Step 3: 학습 시작

1. **"Save"** 클릭 → Experiment가 DRAFT 상태로 저장
2. **"Start Training"** 클릭 → RUNNING 상태로 전환
3. Hub가 자동으로:
   - ExperimentRun 레코드 생성
   - YAML config 생성 (monitor.run_id 자동 주입)
   - `python train.py --config /tmp/exp_N_xxx.yaml` 실행

#### Step 4: 실시간 모니터링

RunMonitor 페이지에서 확인 가능한 항목:

- **Training Losses**: total, contrastive, quantization, balance, consistency, ortho, lcs
- **Learning Rate**: 현재 LR (warmup → cosine decay)
- **Validation Metrics**: mAP (I2T, T2I), Precision@K (P@1, P@5, P@10)
- **Hash Quality**: bit entropy, quantization error
- **System Stats**: GPU util%, GPU memory, CPU%, RAM%
- **Logs**: 학습 프로세스 stdout 실시간 tail

### Scenario B: Stop → Clone → 재학습

#### Step 5: 학습 중지

1. RunMonitor 페이지에서 **"Stop"** 버튼 클릭
2. Hub가 SIGTERM → (5초 대기) → SIGKILL 순으로 프로세스 종료
3. Run 상태가 `CANCELLED`로 변경

#### Step 6: 실험 Clone & 수정

1. 실험 목록으로 돌아가기
2. 중지된 실험의 **"Clone"** 버튼 클릭
3. 새 실험이 "(copy)" 접미사와 함께 DRAFT 상태로 생성
4. Config 수정:
   - **Temperature**: `0.07` → `0.1` (contrastive loss softmax temperature 변경)
   - 나머지는 동일하게 유지
5. **"Save & Start Training"** 클릭

#### Step 7: 두 실험 Compare

1. 실험 목록에서 두 실험을 체크박스로 선택
2. **"Compare"** 버튼 클릭
3. Compare 페이지에서 확인 가능:
   - **Config Diff**: temperature 값만 다름을 확인
   - **Metric Comparison**: 두 실험의 loss curves, mAP curves 오버레이
   - **System Resource Usage**: GPU/CPU 사용량 비교

### Scenario C: 직접 CLI 실행 (Hub 없이 테스트)

Hub의 bridge 엔드포인트만 사용하여 수동으로 테스트할 수도 있습니다.

```bash
# 1. Hub 서버 시작
./scripts/dev.sh

# 2. 별도 터미널에서 vlm_quantization 직접 실행
cd /path/to/vlm_quantization

# config에 monitor 설정 포함
cat > /tmp/test_config.yaml << 'EOF'
model:
  backbone: google/siglip2-so400m-patch14-384
  bit_list: [8, 16, 32, 48, 64, 128]
  hidden_dim: 512
  dropout: 0.1
  freeze_backbone: true

training:
  batch_size: auto
  max_epochs: 5
  hash_lr: 1.0e-3
  backbone_lr: 1.0e-5
  weight_decay: 0.01
  warmup_steps: 500
  gradient_clip_val: 1.0
  accumulate_grad_batches: 4

loss:
  contrastive_weight: 1.0
  ortho_weight: 0.1
  quantization_weight: 0.1
  balance_weight: 0.01
  consistency_weight: 0.5
  lcs_weight: 0.5
  temperature: 0.07
  ema_decay: 0.99

data:
  data_root: ./data/coco
  karpathy_json: ./data/coco/dataset_coco.json
  extra_datasets:
    - jsonl_path: ./data/coco_ko/coco_ko.jsonl
      data_root: ./data/coco
  num_workers: 4
  max_text_length: 64
  image_size: 384

monitor:
  enabled: true
  server_url: http://localhost:8000
  log_every_n_steps: 10
EOF

# 3. 먼저 hub에서 ExperimentRun을 API로 생성
RUN_ID=$(curl -s -X POST http://localhost:8000/api/experiments \
  -H "Content-Type: application/json" \
  -d '{
    "name": "CLI Test Run",
    "schema_id": 1,
    "config_json": {"monitor.enabled": true}
  }' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

echo "Created experiment: $RUN_ID"

# 4. 학습 시작 (run_id를 config에 추가)
uv run python train.py --config /tmp/test_config.yaml

# 5. http://localhost:5173 에서 실시간 모니터링 확인
```

## 4. MonitorCallback 프로토콜 상세

### Training Metrics (매 N step)

MonitorCallback이 보내는 payload:
```json
{
  "run_id": "42",
  "step": 100,
  "epoch": 1,
  "loss_total": 2.345,
  "loss_contrastive": 1.234,
  "loss_quantization": 0.456,
  "loss_balance": 0.012,
  "loss_consistency": 0.321,
  "loss_ortho": 0.098,
  "loss_lcs": 0.224,
  "lr": 0.0003
}
```

Hub bridge가 변환하여 저장:
```json
{
  "type": "metric",
  "run_id": 42,
  "step": 100,
  "epoch": 1,
  "metrics": {
    "loss_total": 2.345,
    "loss_contrastive": 1.234,
    "loss_quantization": 0.456,
    "loss_balance": 0.012,
    "loss_consistency": 0.321,
    "loss_ortho": 0.098,
    "loss_lcs": 0.224,
    "lr": 0.0003
  }
}
```

### Eval Metrics (매 validation epoch)

```json
{
  "run_id": "42",
  "epoch": 1,
  "step": 500,
  "map_i2t": 0.423,
  "map_t2i": 0.398,
  "p1": 0.72,
  "p5": 0.65,
  "p10": 0.58,
  "bit_entropy_64": 0.92,
  "quant_error_64": 0.15,
  "val_loss_total": 2.1
}
```

Hub bridge가 `eval/` prefix 추가하여 저장:
```json
{
  "metrics": {
    "eval/map_i2t": 0.423,
    "eval/map_t2i": 0.398,
    "eval/p1": 0.72,
    "eval/p5": 0.65,
    "eval/p10": 0.58,
    "eval/bit_entropy_64": 0.92,
    "eval/quant_error_64": 0.15,
    "val_loss_total": 2.1
  }
}
```

## 5. Troubleshooting

### MonitorCallback 연결 실패

```
Monitor POST /api/metrics/training failed (1x): Connection refused
```

**원인**: Hub 서버가 실행중이지 않음
**해결**: `./scripts/dev.sh`로 hub 서버 먼저 시작

### run_id 매핑 실패

```
Cannot resolve run_id 'xxx' to an active run
```

**원인**: Hub에서 ExperimentRun을 생성하지 않고 직접 train.py 실행
**해결**:
1. Hub UI에서 실험 생성 후 "Start Training" 사용 (권장)
2. 또는 train.py의 run_id 패치 적용 + monitor.run_id를 config에 명시

### WebSocket 연결 끊김

**증상**: Dashboard에서 메트릭이 업데이트되지 않음
**확인**: 브라우저 DevTools → Network → WS 탭에서 연결 상태 확인
**해결**: 페이지 새로고침 (WebSocket 자동 재연결)

### GPU 메모리 부족

```
CUDA out of memory
```

**해결**: Config에서 다음을 조정:
- `training.batch_size` → `"auto"` (자동 감지) 또는 더 작은 값
- `model.freeze_backbone` → `true` (VRAM 절약)
- `training.accumulate_grad_batches` → 값 증가 (effective batch size 유지)
