import RNConfig from 'react-native-config';

const Config = RNConfig as {
  API_URL?: string;
  NEON_AUTH_URL?: string;
  GOOGLE_WEB_CLIENT_ID?: string;
  GOOGLE_IOS_CLIENT_ID?: string;
};
export const config = {
  API_URL: Config.API_URL || '',
  NEON_AUTH_URL: Config.NEON_AUTH_URL || '',
  GOOGLE_WEB_CLIENT_ID: Config.GOOGLE_WEB_CLIENT_ID || '',
  GOOGLE_IOS_CLIENT_ID: Config.GOOGLE_IOS_CLIENT_ID || '',
};
