/**
 * Smart-Stua Mobile — Root App Component (Expo)
 * ================================================
 * Auth Flow:
 *   1. On launch, `SplashGate` checks SecureStore for a saved token.
 *   2. If a token exists  → navigate straight to MainApp (tab navigator).
 *   3. If no token found  → show Login screen.
 *   4. After login        → LoginScreen calls navigation.reset() to MainApp.
 *   5. Logout (Settings)  → clears SecureStore token, resets back to Login.
 *
 * Stack structure:
 *   RootStack
 *   ├── SplashGate  (hidden — bootstraps auth state)
 *   ├── Login
 *   └── MainApp     (contains the bottom-tab navigator)
 */

import React, { useEffect, useState, useCallback } from 'react';
import { View, ActivityIndicator, StyleSheet } from 'react-native';
import { NavigationContainer }    from '@react-navigation/native';
import { createStackNavigator }   from '@react-navigation/stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { StatusBar }              from 'expo-status-bar';
import { Platform }               from 'react-native';
import { Ionicons }               from '@expo/vector-icons';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import * as SecureStore           from 'expo-secure-store';

// ── Screens ──────────────────────────────────────────────────────────────────
import LoginScreen    from './src/screens/LoginScreen';
import SignUpScreen   from './src/screens/SignUpScreen';
import DashboardScreen  from './src/screens/Dashboard';
import DeviceListScreen from './src/screens/DeviceList';
import AlertHistory     from './src/screens/AlertHistory';
import SettingsScreen   from './src/screens/Settings';

// ── Navigators ───────────────────────────────────────────────────────────────
const RootStack = createStackNavigator();
const Tab       = createBottomTabNavigator();

// ── Design Tokens (match app.json dark theme) ─────────────────────────────────
const C = {
  primary:    '#00D26A',
  background: '#0A0F1E',
  tabBar:     '#0D1526',
  tabInactive:'#4A5568',
};

// ─── Secure Token Key (same constant as LoginScreen & api.js) ─────────────────
const SECURE_TOKEN_KEY = 'smart_stua_auth_token';

// ─── MainApp: Bottom Tab Navigator ───────────────────────────────────────────
// Wrapped in a named component so the Stack can reference it cleanly.
function MainApp() {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerShown: false,
        tabBarStyle: {
          backgroundColor: C.tabBar,
          borderTopColor:  '#1E293B',
          borderTopWidth:  1,
          height:          Platform.OS === 'ios' ? 84 : 64,
          paddingBottom:   Platform.OS === 'ios' ? 24 : 8,
          paddingTop:      8,
        },
        tabBarActiveTintColor:   C.primary,
        tabBarInactiveTintColor: C.tabInactive,
        tabBarLabelStyle: { fontSize: 11, fontWeight: '600' },
        tabBarIcon: ({ focused, color, size }) => {
          const icons = {
            Dashboard: focused ? 'analytics'       : 'analytics-outline',
            Devices:   focused ? 'hardware-chip'   : 'hardware-chip-outline',
            Alerts:    focused ? 'notifications'   : 'notifications-outline',
            Settings:  focused ? 'settings'        : 'settings-outline',
          };
          return <Ionicons name={icons[route.name]} size={size} color={color} />;
        },
      })}
    >
      <Tab.Screen name="Dashboard" component={DashboardScreen} />
      <Tab.Screen name="Devices"   component={DeviceListScreen} />
      <Tab.Screen name="Alerts"    component={AlertHistory} />
      <Tab.Screen name="Settings"  component={SettingsScreen} />
    </Tab.Navigator>
  );
}

// ─── SplashGate: Auth Bootstrap ──────────────────────────────────────────────
/**
 * Shown for a brief moment while we check SecureStore.
 * Immediately navigates away — the user never interacts with this screen.
 * Using a dedicated component avoids polluting the navigator with
 * imperative `useEffect` calls inside App().
 */
function SplashGate({ navigation }) {
  useEffect(() => {
    (async () => {
      try {
        const token = await SecureStore.getItemAsync(SECURE_TOKEN_KEY);
        // `reset` clears the back-stack entirely, preventing the user from
        // navigating back to SplashGate with the hardware back button.
        navigation.reset({
          index: 0,
          routes: [{ name: token ? 'MainApp' : 'Login' }],
        });
      } catch {
        // If SecureStore fails for any reason, default to Login
        navigation.reset({ index: 0, routes: [{ name: 'Login' }] });
      }
    })();
  }, [navigation]);

  // Minimal loading UI while the async check runs
  return (
    <View style={splash.container}>
      <ActivityIndicator size="large" color={C.primary} />
    </View>
  );
}

const splash = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: C.background,
    alignItems: 'center',
    justifyContent: 'center',
  },
});

// ─── Root App Component ───────────────────────────────────────────────────────
export default function App() {
  return (
    <GestureHandlerRootView style={{ flex: 1, backgroundColor: C.background }}>
      <StatusBar style="light" backgroundColor={C.background} />
      <NavigationContainer>
        <RootStack.Navigator
          // No header chrome on any screen in this stack
          screenOptions={{ headerShown: false }}
          // Start on SplashGate — it redirects immediately after checking token
          initialRouteName="SplashGate"
        >
          {/* Auth bootstrap — invisible to the user */}
          <RootStack.Screen name="SplashGate" component={SplashGate} />

          {/* Unauthenticated */}
          <RootStack.Screen
            name="Login"
            component={LoginScreen}
            options={{
              // Slide-from-bottom feel for the login screen
              animationTypeForReplace: 'pop',
            }}
          />

          <RootStack.Screen
            name="SignUp"
            component={SignUpScreen}
          />

          {/* Authenticated — wraps the full tab navigator */}
          <RootStack.Screen name="MainApp" component={MainApp} />
        </RootStack.Navigator>
      </NavigationContainer>
    </GestureHandlerRootView>
  );
}
