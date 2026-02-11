import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // 로컬 개발: 상위 디렉토리의 .env에서 GOOGLE_* 로드
  const env = loadEnv(mode, process.cwd() + '/..', 'GOOGLE_')
  // Docker: process.env에서 직접 전달받은 값 우선 사용
  const googleClientId = process.env.GOOGLE_CLIENT_ID || env.GOOGLE_CLIENT_ID || ''

  return {
    plugins: [react()],
    define: {
      'import.meta.env.VITE_GOOGLE_CLIENT_ID': JSON.stringify(googleClientId),
    },
  }
})
