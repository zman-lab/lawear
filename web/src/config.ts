/** GitHub 연동 설정 */
export const GITHUB_OWNER = 'zman-lab';
export const GITHUB_REPO = 'lawear';
export const GITHUB_API = 'https://api.github.com';

/**
 * Fine-grained PAT (issues:write 만 허용)
 * 빌드 시 VITE_GITHUB_TOKEN 환경변수로 주입
 * 없으면 크래시 리포트 전송만 비활성 (버전 확인은 토큰 불필요)
 */
export const GITHUB_TOKEN = import.meta.env.VITE_GITHUB_TOKEN ?? '';
