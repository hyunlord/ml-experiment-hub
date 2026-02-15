"""Service for managing git credentials."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from backend.models.experiment import GitCredential
from backend.schemas.project import GitCredentialCreate, GitCredentialResponse


def mask_token(token: str) -> str:
    """Mask a token showing only first 4 and last 4 characters."""
    if len(token) <= 8:
        return "****"
    return f"{token[:4]}{'*' * (len(token) - 8)}{token[-4:]}"


class GitCredentialService:
    """Service for managing git credentials."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_credentials(self) -> list[GitCredentialResponse]:
        result = await self.session.execute(
            select(GitCredential).order_by(GitCredential.created_at.desc())
        )
        credentials = result.scalars().all()
        return [
            GitCredentialResponse(
                id=c.id,  # type: ignore[arg-type]
                name=c.name,
                provider=c.provider,
                token_masked=mask_token(c.token),
                created_at=c.created_at,
            )
            for c in credentials
        ]

    async def create_credential(self, data: GitCredentialCreate) -> GitCredentialResponse:
        cred = GitCredential(
            name=data.name,
            provider=data.provider,
            token=data.token,
        )
        self.session.add(cred)
        await self.session.commit()
        await self.session.refresh(cred)
        return GitCredentialResponse(
            id=cred.id,  # type: ignore[arg-type]
            name=cred.name,
            provider=cred.provider,
            token_masked=mask_token(cred.token),
            created_at=cred.created_at,
        )

    async def delete_credential(self, credential_id: int) -> bool:
        result = await self.session.execute(
            select(GitCredential).where(GitCredential.id == credential_id)
        )
        cred = result.scalar_one_or_none()
        if not cred:
            return False
        await self.session.delete(cred)
        await self.session.commit()
        return True
