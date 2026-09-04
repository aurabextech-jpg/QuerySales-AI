declare module 'react-native-config' {
  export interface NativeConfig {
    API_URL?: string;
    NEON_AUTH_URL?: string;
  }
  
  export const Config: NativeConfig;
  export default Config;
}
