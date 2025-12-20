/**
 * PROVENIQ Ops - Configuration
 */

export const config = {
  // API Configuration
  api: {
    // Development: Use your local machine's IP for physical device testing
    // Find your IP: ipconfig (Windows) or ifconfig (Mac/Linux)
    baseUrl: __DEV__ 
      ? 'http://192.168.1.100:8000'  // Replace with your machine's IP
      : 'https://api.proveniq-ops.com',
    timeout: 10000,
  },
  
  // Firebase Configuration (for auth)
  firebase: {
    apiKey: 'YOUR_FIREBASE_API_KEY',
    authDomain: 'YOUR_PROJECT.firebaseapp.com',
    projectId: 'YOUR_PROJECT_ID',
  },
  
  // App Settings
  app: {
    name: 'PROVENIQ Ops',
    version: '1.0.0',
  },
};

// Helper to update API URL at runtime (for settings screen)
export let runtimeApiUrl: string | null = null;

export function setRuntimeApiUrl(url: string) {
  runtimeApiUrl = url;
}

export function getApiUrl(): string {
  return runtimeApiUrl || config.api.baseUrl;
}
