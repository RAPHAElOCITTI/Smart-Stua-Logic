import * as Notifications from 'expo-notifications';
import * as Device from 'expo-device';
import Constants from 'expo-constants';
import { Platform } from 'react-native';
import api from '../api';

// Configure how notifications behave when the app is foregrounded
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

export async function registerForPushNotificationsAsync() {
  let token;

  try {
    if (Platform.OS === 'android') {
      await Notifications.setNotificationChannelAsync('default', {
        name: 'default',
        importance: Notifications.AndroidImportance.MAX,
        vibrationPattern: [0, 250, 250, 250],
        lightColor: '#00D26A',
      });
    }

    if (Device.isDevice) {
      const { status: existingStatus } = await Notifications.getPermissionsAsync();
      let finalStatus = existingStatus;
      if (existingStatus !== 'granted') {
        const { status } = await Notifications.requestPermissionsAsync();
        finalStatus = status;
      }
      if (finalStatus !== 'granted') {
        console.warn('Failed to get push token for push notification!');
        return null;
      }

      // Retrieve Project ID from app config dynamically
      const projectId =
        Constants.expoConfig?.extra?.eas?.projectId ??
        Constants.easConfig?.projectId;

      if (!projectId) {
        console.warn(
          '[Push Notifications] EAS Project ID not found in app.json.\n' +
          'To receive push notifications, please run "eas project:init" ' +
          'or configure extra.eas.projectId inside your app.json under "expo".'
        );
      }
      
      // Fetch token (uses EAS project ID if available)
      token = (await Notifications.getExpoPushTokenAsync({ projectId })).data;
    } else {
      console.log('Must use physical device for Push Notifications');
    }
  } catch (error) {
    console.warn('Error registering for push notifications:', error);
  }

  return token;
}

export async function syncPushTokenWithBackend() {
  try {
    const token = await registerForPushNotificationsAsync();
    if (token) {
      await api.post('/auth/save-push-token/', { push_token: token });
      console.log('Push token synced with backend successfully:', token);
    }
  } catch (err) {
    console.error('Failed to sync push token with backend:', err.message);
  }
}
