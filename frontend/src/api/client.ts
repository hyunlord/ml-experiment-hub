import axios from 'axios'

const client = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
})

// Extract server error messages instead of generic "Request failed with status code 500"
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (axios.isAxiosError(error) && error.response?.data) {
      const data = error.response.data;
      // FastAPI returns {"detail": "..."} for HTTP errors
      const message =
        typeof data.detail === 'string'
          ? data.detail
          : typeof data.message === 'string'
            ? data.message
            : typeof data === 'string'
              ? data
              : error.message;
      const enhanced = new Error(message);
      (enhanced as any).status = error.response.status;
      (enhanced as any).response = error.response;
      return Promise.reject(enhanced);
    }
    return Promise.reject(error);
  }
)

export default client
