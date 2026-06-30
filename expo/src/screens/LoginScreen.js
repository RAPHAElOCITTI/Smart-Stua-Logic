/**
 * Smart-Stua Mobile — LoginScreen.js
 * =====================================
 * Authenticates against POST /api/auth/login/ on the Django backend.
 * On success, the DRF auth token is saved SECURELY via expo-secure-store
 * (NOT AsyncStorage — tokens are sensitive and should never live in
 * unencrypted key-value storage).
 *
 * Token storage strategy:
 *  - expo-secure-store  → stores the DRF auth token (encrypted on-device)
 *  - AsyncStorage       → stores non-sensitive prefs (base URL, etc.)
 *
 * Navigation: uses navigation.reset() to MainApp so the user cannot press
 * "back" to return to Login once authenticated.
 */

import React, { useState, useRef } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  KeyboardAvoidingView,
  Keyboard,
  Platform,
  ScrollView,
  StatusBar,
  Dimensions,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import * as SecureStore from 'expo-secure-store';
import { login } from '../api';
import { syncPushTokenWithBackend } from '../utils/notifications';

// ─── Secure Storage Key ────────────────────────────────────────────────────────
// Must be identical in api.js and App.js to ensure the token round-trips correctly.
export const SECURE_TOKEN_KEY = 'smart_stua_auth_token';

// ─── Design Tokens ────────────────────────────────────────────────────────────
const C = {
  bg: '#0A0F1E',
  bgCard: '#0D1526',
  primary: '#00D26A',
  primaryDark: '#00A855',
  accent: '#00B4D8',
  danger: '#FF3B30',
  textPrimary: '#F1F5F9',
  textSecondary: '#94A3B8',
  border: '#1E293B',
  borderFocus: '#00D26A',
  inputBg: '#111827',
};

const { height: SCREEN_HEIGHT } = Dimensions.get('window');

export default function LoginScreen({ navigation }) {
  // ─── Form State ─────────────────────────────────────────────────────────────
  const [phoneNumber, setPhoneNumber] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  // ─── UI State ────────────────────────────────────────────────────────────────
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [focusedField, setFocusedField] = useState(null);

  // ─── Focus Refs ───────────────────────────────────────────────────────────────
  // Enables keyboard's "Next" action to chain focus between fields.
  const passwordRef = useRef(null);

  // ─── Login Handler ────────────────────────────────────────────────────────────
  const handleLogin = async () => {
    Keyboard.dismiss();

    // Basic client-side validation
    if (!phoneNumber.trim()) {
      setError('Phone number is required.');
      return;
    }
    if (!password) {
      setError('Password is required.');
      return;
    }

    setError('');
    setLoading(true);

    try {
      /**
       * POST /api/auth/login/
       * Body: { phone_number, password }
       * Success 200: { token: "abc123...", user: { ... } }
       * Failure 401: { error: "Invalid credentials" }
       */
      const data = await login({
        phone_number: phoneNumber.trim(),
        password,
      });

      // ── Secure Token Storage ──────────────────────────────────────────────
      // expo-secure-store encrypts values using the device's secure enclave
      // (Keychain on iOS, EncryptedSharedPreferences on Android).
      const token = data.token || data.access || data.key;
      if (token) {
        await SecureStore.setItemAsync(SECURE_TOKEN_KEY, token);
      } else {
        throw new Error('No authentication token received from server.');
      }

      // Sync push token asynchronously — fire-and-forget, never block navigation
      syncPushTokenWithBackend().catch(() => { });

      // ── Navigation Handoff ────────────────────────────────────────────────
      // `reset` removes LoginScreen from the stack so back-press goes to OS home.
      navigation.reset({
        index: 0,
        routes: [{ name: 'MainApp' }],
      });

    } catch (err) {
      // Surface backend error message (DRF returns { "error": "..." })
      const msg =
        err?.response?.data?.error ||
        err?.response?.data?.detail ||
        err?.message;

      if (!msg || msg === 'Network request failed' || msg.includes('network')) {
        setError('Cannot reach the server. Check your Wi-Fi and ensure the backend is running.');
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  };

  // ─── Focus helpers ────────────────────────────────────────────────────────────
  const inputStyle = (field) => [
    styles.inputWrapper,
    focusedField === field && styles.inputWrapperFocused,
  ];

  const iconColor = (field) =>
    focusedField === field ? C.primary : C.textSecondary;

  // ─── Render ───────────────────────────────────────────────────────────────────
  return (
    <View style={styles.root}>
      <StatusBar barStyle="light-content" backgroundColor={C.bg} />

      {Platform.OS === 'ios' ? (
        <KeyboardAvoidingView
          style={{ flex: 1 }}
          behavior="padding"
          keyboardVerticalOffset={20}
        >
          <ScrollView
            contentContainerStyle={styles.scrollIOS}
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}
            bounces={false}
            overScrollMode="never"
          >
            <View style={styles.innerContainer}>

              {/* ── Header / Branding ── */}
              <View style={styles.header}>
                <LinearGradient
                  colors={[C.primary + '33', C.accent + '1A']}
                  style={styles.logoRing}
                  start={{ x: 0, y: 0 }}
                  end={{ x: 1, y: 1 }}
                >
                  <Ionicons name="leaf" size={40} color={C.primary} />
                </LinearGradient>

                <Text style={styles.appName}>Smart-Stua</Text>
                <Text style={styles.tagline}>Aflatoxin Prevention System</Text>
              </View>

              {/* ── Card ── */}
              <View style={styles.card}>
                <Text style={styles.cardTitle}>Sign In</Text>
                <Text style={styles.cardSubtitle}>
                  Enter your credentials to access the monitoring dashboard
                </Text>

                {/* ── Error Banner ── */}
                {!!error && (
                  <View style={styles.errorBanner}>
                    <Ionicons name="alert-circle" size={16} color={C.danger} />
                    <Text style={styles.errorText}>{error}</Text>
                  </View>
                )}

                {/* ── Phone Number Field ── */}
                <View style={styles.fieldGroup}>
                  <Text style={styles.label}>Phone Number</Text>
                  <View style={inputStyle('phone')}>
                    <Ionicons
                      name="call-outline"
                      size={18}
                      color={iconColor('phone')}
                      style={styles.inputIcon}
                    />
                    <TextInput
                      style={styles.input}
                      placeholder="+256 700 000 000"
                      placeholderTextColor={C.textSecondary}
                      value={phoneNumber}
                      onChangeText={text => { setPhoneNumber(text); if (error) setError(''); }}
                      onFocus={() => setFocusedField('phone')}
                      onBlur={() => setFocusedField(null)}
                      keyboardType="phone-pad"
                      autoCapitalize="none"
                      autoCorrect={false}
                      returnKeyType="next"
                      onSubmitEditing={() => passwordRef.current?.focus()}
                      blurOnSubmit={false}
                      editable={!loading}
                      testID="input-phone"
                    />
                  </View>
                </View>

                {/* ── Password Field ── */}
                <View style={styles.fieldGroup}>
                  <Text style={styles.label}>Password</Text>
                  <View style={inputStyle('password')}>
                    <Ionicons
                      name="lock-closed-outline"
                      size={18}
                      color={iconColor('password')}
                      style={styles.inputIcon}
                    />
                    <TextInput
                      ref={passwordRef}
                      style={[styles.input, { flex: 1 }]}
                      placeholder="••••••••"
                      placeholderTextColor={C.textSecondary}
                      value={password}
                      onChangeText={text => { setPassword(text); if (error) setError(''); }}
                      onFocus={() => setFocusedField('password')}
                      onBlur={() => setFocusedField(null)}
                      secureTextEntry={!showPassword}
                      autoCapitalize="none"
                      autoCorrect={false}
                      returnKeyType="done"
                      onSubmitEditing={handleLogin}
                      editable={!loading}
                      testID="input-password"
                    />
                    <TouchableOpacity
                      onPress={() => setShowPassword(v => !v)}
                      style={styles.eyeBtn}
                      hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                      activeOpacity={0.7}
                    >
                      <Ionicons
                        name={showPassword ? 'eye-off-outline' : 'eye-outline'}
                        size={18}
                        color={C.textSecondary}
                      />
                    </TouchableOpacity>
                  </View>
                </View>

                {/* ── Submit Button ── */}
                <TouchableOpacity
                  onPress={handleLogin}
                  disabled={loading}
                  activeOpacity={0.85}
                  style={styles.btnContainer}
                  testID="btn-login"
                >
                  <LinearGradient
                    colors={loading ? ['#1E3A2F', '#1E3A2F'] : [C.primary, C.primaryDark]}
                    style={styles.btn}
                    start={{ x: 0, y: 0 }}
                    end={{ x: 1, y: 0 }}
                  >
                    {loading ? (
                      <View style={styles.btnInner}>
                        <ActivityIndicator size="small" color={C.primary} />
                        <Text style={[styles.btnText, { color: C.primary, marginLeft: 8 }]}>
                          Signing In…
                        </Text>
                      </View>
                    ) : (
                      <View style={styles.btnInner}>
                        <Text style={styles.btnText}>Sign In</Text>
                        <Ionicons name="arrow-forward" size={18} color="#000" style={{ marginLeft: 6 }} />
                      </View>
                    )}
                  </LinearGradient>
                </TouchableOpacity>
              </View>

              {/* ── Footer ── */}
              <View style={styles.footer}>
                <TouchableOpacity
                  onPress={() => {
                    Keyboard.dismiss();
                    navigation.navigate('SignUp');
                  }}
                  style={{ marginBottom: 12 }}
                  activeOpacity={0.7}
                >
                  <Text style={{ color: C.textSecondary, fontSize: 14 }}>
                    Don't have an account?{' '}
                    <Text style={{ color: C.primary, fontWeight: '700' }}>Sign Up</Text>
                  </Text>
                </TouchableOpacity>

                <View style={styles.securityBadge}>
                  <Ionicons name="shield-checkmark-outline" size={13} color={C.primary} />
                  <Text style={styles.securityText}>Encrypted secure storage</Text>
                </View>
                <Text style={styles.footerNote}>
                  Access restricted to authorized personnel only
                </Text>
              </View>

            </View>
          </ScrollView>
        </KeyboardAvoidingView>
      ) : (
        <View style={{ flex: 1 }}>
          <ScrollView
            contentContainerStyle={styles.scrollAndroid}
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}
            bounces={false}
            overScrollMode="never"
          >
            <View style={styles.innerContainer}>

              {/* ── Header / Branding ── */}
              <View style={styles.header}>
                <LinearGradient
                  colors={[C.primary + '33', C.accent + '1A']}
                  style={styles.logoRing}
                  start={{ x: 0, y: 0 }}
                  end={{ x: 1, y: 1 }}
                >
                  <Ionicons name="leaf" size={40} color={C.primary} />
                </LinearGradient>

                <Text style={styles.appName}>Smart-Stua</Text>
                <Text style={styles.tagline}>Aflatoxin Prevention System</Text>
              </View>

              {/* ── Card ── */}
              <View style={styles.card}>
                <Text style={styles.cardTitle}>Sign In</Text>
                <Text style={styles.cardSubtitle}>
                  Enter your credentials to access the monitoring dashboard
                </Text>

                {/* ── Error Banner ── */}
                {!!error && (
                  <View style={styles.errorBanner}>
                    <Ionicons name="alert-circle" size={16} color={C.danger} />
                    <Text style={styles.errorText}>{error}</Text>
                  </View>
                )}

                {/* ── Phone Number Field ── */}
                <View style={styles.fieldGroup}>
                  <Text style={styles.label}>Phone Number</Text>
                  <View style={inputStyle('phone')}>
                    <Ionicons
                      name="call-outline"
                      size={18}
                      color={iconColor('phone')}
                      style={styles.inputIcon}
                    />
                    <TextInput
                      style={styles.input}
                      placeholder="+256 700 000 000"
                      placeholderTextColor={C.textSecondary}
                      value={phoneNumber}
                      onChangeText={text => { setPhoneNumber(text); if (error) setError(''); }}
                      onFocus={() => setFocusedField('phone')}
                      onBlur={() => setFocusedField(null)}
                      keyboardType="phone-pad"
                      autoCapitalize="none"
                      autoCorrect={false}
                      returnKeyType="next"
                      onSubmitEditing={() => passwordRef.current?.focus()}
                      blurOnSubmit={false}
                      editable={!loading}
                      testID="input-phone"
                    />
                  </View>
                </View>

                {/* ── Password Field ── */}
                <View style={styles.fieldGroup}>
                  <Text style={styles.label}>Password</Text>
                  <View style={inputStyle('password')}>
                    <Ionicons
                      name="lock-closed-outline"
                      size={18}
                      color={iconColor('password')}
                      style={styles.inputIcon}
                    />
                    <TextInput
                      ref={passwordRef}
                      style={[styles.input, { flex: 1 }]}
                      placeholder="••••••••"
                      placeholderTextColor={C.textSecondary}
                      value={password}
                      onChangeText={text => { setPassword(text); if (error) setError(''); }}
                      onFocus={() => setFocusedField('password')}
                      onBlur={() => setFocusedField(null)}
                      secureTextEntry={!showPassword}
                      autoCapitalize="none"
                      autoCorrect={false}
                      returnKeyType="done"
                      onSubmitEditing={handleLogin}
                      editable={!loading}
                      testID="input-password"
                    />
                    <TouchableOpacity
                      onPress={() => setShowPassword(v => !v)}
                      style={styles.eyeBtn}
                      hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                      activeOpacity={0.7}
                    >
                      <Ionicons
                        name={showPassword ? 'eye-off-outline' : 'eye-outline'}
                        size={18}
                        color={C.textSecondary}
                      />
                    </TouchableOpacity>
                  </View>
                </View>

                {/* ── Submit Button ── */}
                <TouchableOpacity
                  onPress={handleLogin}
                  disabled={loading}
                  activeOpacity={0.85}
                  style={styles.btnContainer}
                  testID="btn-login"
                >
                  <LinearGradient
                    colors={loading ? ['#1E3A2F', '#1E3A2F'] : [C.primary, C.primaryDark]}
                    style={styles.btn}
                    start={{ x: 0, y: 0 }}
                    end={{ x: 1, y: 0 }}
                  >
                    {loading ? (
                      <View style={styles.btnInner}>
                        <ActivityIndicator size="small" color={C.primary} />
                        <Text style={[styles.btnText, { color: C.primary, marginLeft: 8 }]}>
                          Signing In…
                        </Text>
                      </View>
                    ) : (
                      <View style={styles.btnInner}>
                        <Text style={styles.btnText}>Sign In</Text>
                        <Ionicons name="arrow-forward" size={18} color="#000" style={{ marginLeft: 6 }} />
                      </View>
                    )}
                  </LinearGradient>
                </TouchableOpacity>
              </View>

              {/* ── Footer ── */}
              <View style={styles.footer}>
                <TouchableOpacity
                  onPress={() => {
                    Keyboard.dismiss();
                    navigation.navigate('SignUp');
                  }}
                  style={{ marginBottom: 12 }}
                  activeOpacity={0.7}
                >
                  <Text style={{ color: C.textSecondary, fontSize: 14 }}>
                    Don't have an account?{' '}
                    <Text style={{ color: C.primary, fontWeight: '700' }}>Sign Up</Text>
                  </Text>
                </TouchableOpacity>

                <View style={styles.securityBadge}>
                  <Ionicons name="shield-checkmark-outline" size={13} color={C.primary} />
                  <Text style={styles.securityText}>Encrypted secure storage</Text>
                </View>
                <Text style={styles.footerNote}>
                  Access restricted to authorized personnel only
                </Text>
              </View>

            </View>
          </ScrollView>
        </View>
      )}
    </View>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────
const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: C.bg,
  },
  // iOS: minHeight forces full-screen layout so header is never clipped.
  // Android (Samsung): flexGrow only — minHeight prevents the view from
  // shrinking when the soft keyboard appears, causing inputs to stay hidden.
  scrollIOS: {
    flexGrow: 1,
    minHeight: SCREEN_HEIGHT,
  },
  scrollAndroid: {
    flexGrow: 1,
  },
  innerContainer: {
    flex: 1,
    paddingHorizontal: 24,
    paddingTop: 48,
    paddingBottom: 32,
  },

  // Header
  header: {
    alignItems: 'center',
    marginBottom: 36,
  },
  logoRing: {
    width: 88,
    height: 88,
    borderRadius: 44,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 18,
    borderWidth: 1,
    borderColor: C.primary + '40',
  },
  appName: {
    fontSize: 30,
    fontWeight: '800',
    color: C.textPrimary,
    letterSpacing: 0.5,
  },
  tagline: {
    fontSize: 13,
    color: C.textSecondary,
    marginTop: 4,
    letterSpacing: 0.3,
  },

  // Card
  card: {
    backgroundColor: C.bgCard,
    borderRadius: 20,
    padding: 28,
    borderWidth: 1,
    borderColor: C.border,
  },
  cardTitle: {
    fontSize: 22,
    fontWeight: '700',
    color: C.textPrimary,
    marginBottom: 6,
  },
  cardSubtitle: {
    fontSize: 13,
    color: C.textSecondary,
    marginBottom: 24,
    lineHeight: 19,
  },

  // Error
  errorBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: C.danger + '1A',
    borderWidth: 1,
    borderColor: C.danger + '50',
    borderRadius: 10,
    padding: 12,
    marginBottom: 20,
    gap: 8,
  },
  errorText: {
    flex: 1,
    color: C.danger,
    fontSize: 13,
    lineHeight: 18,
  },

  // Inputs
  fieldGroup: {
    marginBottom: 16,
  },
  label: {
    fontSize: 13,
    fontWeight: '600',
    color: C.textSecondary,
    marginBottom: 8,
    letterSpacing: 0.2,
  },
  inputWrapper: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: C.inputBg,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: C.border,
    paddingHorizontal: 14,
    height: 52,
  },
  inputWrapperFocused: {
    borderColor: C.borderFocus,
    shadowColor: C.primary,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.25,
    shadowRadius: 8,
    elevation: 4,
  },
  inputIcon: {
    marginRight: 10,
  },
  input: {
    flex: 1,
    color: C.textPrimary,
    fontSize: 15,
  },
  eyeBtn: {
    padding: 4,
  },

  // Button
  btnContainer: {
    marginTop: 8,
    borderRadius: 14,
    overflow: 'hidden',
  },
  btn: {
    height: 54,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 14,
  },
  btnInner: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  btnText: {
    color: '#000',
    fontSize: 16,
    fontWeight: '700',
    letterSpacing: 0.3,
  },

  // Footer
  footer: {
    alignItems: 'center',
    marginTop: 28,
    gap: 8,
  },
  securityBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    backgroundColor: C.primary + '15',
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderRadius: 20,
  },
  securityText: {
    color: C.primary,
    fontSize: 12,
    fontWeight: '500',
  },
  footerNote: {
    color: C.textSecondary,
    fontSize: 12,
  },
});
