/**
 * Smart-Stua Mobile — SignUpScreen.js
 * =====================================
 * Registers a new user against POST /api/auth/register/ on the Django backend.
 * Provides a selection for Farmer or Store Manager role.
 */

import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  TouchableWithoutFeedback,
  StyleSheet,
  ActivityIndicator,
  KeyboardAvoidingView,
  Keyboard,
  Platform,
  ScrollView,
  StatusBar,
  Alert,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { register } from '../api';

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

export default function SignUpScreen({ navigation }) {
  // ─── Form State ─────────────────────────────────────────────────────────────
  const [fullName, setFullName] = useState('');
  const [phoneNumber, setPhoneNumber] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('farmer'); // Default to farmer
  const [showPassword, setShowPassword] = useState(false);

  // ─── UI State ────────────────────────────────────────────────────────────────
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [focusedField, setFocusedField] = useState(null);

  // ─── Registration Handler ────────────────────────────────────────────────────
  const handleSignUp = async () => {
    if (!fullName.trim()) {
      setError('Full name is required.');
      return;
    }
    if (!phoneNumber.trim()) {
      setError('Phone number is required.');
      return;
    }
    if (!password) {
      setError('Password is required.');
      return;
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }

    setError('');
    setLoading(true);

    try {
      await register({
        full_name: fullName.trim(),
        phone_number: phoneNumber.trim(),
        email: email.trim() || undefined,
        password: password,
        role: role,
      });

      Alert.alert(
        'Registration Successful',
        'Your account has been created. Please sign in.',
        [{ text: 'OK', onPress: () => navigation.navigate('Login') }]
      );
    } catch (err) {
      if (err.response && err.response.data) {
        // Extract validation errors from DRF
        const details = err.response.data;
        let errMsg = '';
        if (typeof details === 'object') {
          errMsg = Object.entries(details)
            .map(([field, msgs]) => `${field}: ${Array.isArray(msgs) ? msgs.join(' ') : msgs}`)
            .join('\n');
        } else {
          errMsg = details;
        }
        setError(errMsg || 'Registration failed.');
      } else if (err.message === 'Network request failed' || err.message.includes('Network')) {
        setError('Cannot reach the server. Check your Wi-Fi/network connection.');
      } else {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={styles.root}>
      <StatusBar barStyle="light-content" backgroundColor={C.bg} />

      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior="padding"
        keyboardVerticalOffset={Platform.OS === 'ios' ? 20 : 0}
        enabled
      >
        <ScrollView
          contentContainerStyle={styles.scroll}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
          bounces={false}
        >
          <TouchableWithoutFeedback onPress={Keyboard.dismiss} accessible={false}>
            <View style={styles.innerContainer}>
              {/* ── Header ── */}
              <View style={styles.header}>
                <LinearGradient
                  colors={[C.primary + '33', C.accent + '1A']}
                  style={styles.logoRing}
                  start={{ x: 0, y: 0 }}
                  end={{ x: 1, y: 1 }}
                >
                  <Ionicons name="person-add" size={32} color={C.primary} />
                </LinearGradient>
                <Text style={styles.appName}>Create Account</Text>
                <Text style={styles.tagline}>Smart-Stua Monitoring Network</Text>
              </View>

              {/* ── Card ── */}
              <View style={styles.card}>
                {/* ── Error Banner ── */}
                {!!error && (
                  <View style={styles.errorBanner}>
                    <Ionicons name="alert-circle" size={16} color={C.danger} />
                    <Text style={styles.errorText}>{error}</Text>
                  </View>
                )}

                {/* ── Full Name Field ── */}
                <View style={styles.fieldGroup}>
                  <Text style={styles.label}>Full Name</Text>
                  <View
                    style={[
                      styles.inputWrapper,
                      focusedField === 'fullName' && styles.inputWrapperFocused,
                    ]}
                  >
                    <Ionicons
                      name="person-outline"
                      size={18}
                      color={focusedField === 'fullName' ? C.primary : C.textSecondary}
                      style={styles.inputIcon}
                    />
                    <TextInput
                      style={styles.input}
                      placeholder="Enter full name"
                      placeholderTextColor={C.textSecondary}
                      value={fullName}
                      onChangeText={text => {
                        setFullName(text);
                        if (error) setError('');
                      }}
                      onFocus={() => setFocusedField('fullName')}
                      onBlur={() => setFocusedField(null)}
                      autoCapitalize="words"
                      autoCorrect={false}
                      returnKeyType="next"
                      editable={!loading}
                    />
                  </View>
                </View>

                {/* ── Phone Number Field ── */}
                <View style={styles.fieldGroup}>
                  <Text style={styles.label}>Phone Number</Text>
                  <View
                    style={[
                      styles.inputWrapper,
                      focusedField === 'phone' && styles.inputWrapperFocused,
                    ]}
                  >
                    <Ionicons
                      name="call-outline"
                      size={18}
                      color={focusedField === 'phone' ? C.primary : C.textSecondary}
                      style={styles.inputIcon}
                    />
                    <TextInput
                      style={styles.input}
                      placeholder="+256 700 000 000"
                      placeholderTextColor={C.textSecondary}
                      value={phoneNumber}
                      onChangeText={text => {
                        setPhoneNumber(text);
                        if (error) setError('');
                      }}
                      onFocus={() => setFocusedField('phone')}
                      onBlur={() => setFocusedField(null)}
                      keyboardType="phone-pad"
                      autoCapitalize="none"
                      autoCorrect={false}
                      returnKeyType="next"
                      editable={!loading}
                    />
                  </View>
                </View>

                {/* ── Email Field (Optional) ── */}
                <View style={styles.fieldGroup}>
                  <Text style={styles.label}>Email Address (Optional)</Text>
                  <View
                    style={[
                      styles.inputWrapper,
                      focusedField === 'email' && styles.inputWrapperFocused,
                    ]}
                  >
                    <Ionicons
                      name="mail-outline"
                      size={18}
                      color={focusedField === 'email' ? C.primary : C.textSecondary}
                      style={styles.inputIcon}
                    />
                    <TextInput
                      style={styles.input}
                      placeholder="name@domain.com"
                      placeholderTextColor={C.textSecondary}
                      value={email}
                      onChangeText={text => {
                        setEmail(text);
                        if (error) setError('');
                      }}
                      onFocus={() => setFocusedField('email')}
                      onBlur={() => setFocusedField(null)}
                      keyboardType="email-address"
                      autoCapitalize="none"
                      autoCorrect={false}
                      returnKeyType="next"
                      editable={!loading}
                    />
                  </View>
                </View>

                {/* ── Password Field ── */}
                <View style={styles.fieldGroup}>
                  <Text style={styles.label}>Password</Text>
                  <View
                    style={[
                      styles.inputWrapper,
                      focusedField === 'password' && styles.inputWrapperFocused,
                    ]}
                  >
                    <Ionicons
                      name="lock-closed-outline"
                      size={18}
                      color={focusedField === 'password' ? C.primary : C.textSecondary}
                      style={styles.inputIcon}
                    />
                    <TextInput
                      style={[styles.input, { flex: 1 }]}
                      placeholder="Min. 8 characters"
                      placeholderTextColor={C.textSecondary}
                      value={password}
                      onChangeText={text => {
                        setPassword(text);
                        if (error) setError('');
                      }}
                      onFocus={() => setFocusedField('password')}
                      onBlur={() => setFocusedField(null)}
                      secureTextEntry={!showPassword}
                      autoCapitalize="none"
                      autoCorrect={false}
                      returnKeyType="done"
                      editable={!loading}
                    />
                    <TouchableOpacity
                      onPress={() => setShowPassword(v => !v)}
                      style={styles.eyeBtn}
                      hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                    >
                      <Ionicons
                        name={showPassword ? 'eye-off-outline' : 'eye-outline'}
                        size={18}
                        color={C.textSecondary}
                      />
                    </TouchableOpacity>
                  </View>
                </View>

                {/* ── Role Selector ── */}
                <View style={styles.fieldGroup}>
                  <Text style={styles.label}>Assign Role</Text>
                  <View style={styles.roleContainer}>
                    <TouchableOpacity
                      activeOpacity={0.8}
                      style={[
                        styles.roleButton,
                        role === 'farmer' && styles.roleButtonActive,
                      ]}
                      onPress={() => setRole('farmer')}
                      disabled={loading}
                    >
                      <Ionicons
                        name="leaf-outline"
                        size={20}
                        color={role === 'farmer' ? '#000' : C.textSecondary}
                      />
                      <Text
                        style={[
                          styles.roleButtonText,
                          role === 'farmer' && styles.roleButtonTextActive,
                        ]}
                      >
                        Farmer
                      </Text>
                    </TouchableOpacity>

                    <TouchableOpacity
                      activeOpacity={0.8}
                      style={[
                        styles.roleButton,
                        role === 'store_manager' && styles.roleButtonActive,
                      ]}
                      onPress={() => setRole('store_manager')}
                      disabled={loading}
                    >
                      <Ionicons
                        name="business-outline"
                        size={20}
                        color={role === 'store_manager' ? '#000' : C.textSecondary}
                      />
                      <Text
                        style={[
                          styles.roleButtonText,
                          role === 'store_manager' && styles.roleButtonTextActive,
                        ]}
                      >
                        Store Manager
                      </Text>
                    </TouchableOpacity>
                  </View>
                </View>

                {/* ── Submit Button ── */}
                <TouchableOpacity
                  onPress={handleSignUp}
                  disabled={loading}
                  activeOpacity={0.85}
                  style={styles.btnContainer}
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
                          Creating Account…
                        </Text>
                      </View>
                    ) : (
                      <View style={styles.btnInner}>
                        <Text style={styles.btnText}>Register</Text>
                        <Ionicons name="checkmark" size={18} color="#000" style={{ marginLeft: 6 }} />
                      </View>
                    )}
                  </LinearGradient>
                </TouchableOpacity>
              </View>

              {/* ── Footer Link ── */}
              <View style={styles.footer}>
                <TouchableOpacity onPress={() => navigation.navigate('Login')}>
                  <Text style={styles.signInLink}>
                    Already have an account? <Text style={{ color: C.primary, fontWeight: '700' }}>Sign In</Text>
                  </Text>
                </TouchableOpacity>
              </View>
            </View>
          </TouchableWithoutFeedback>
        </ScrollView>
      </KeyboardAvoidingView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: C.bg,
  },
  scroll: {
    flexGrow: 1,
  },
  innerContainer: {
    flexGrow: 1,
    paddingHorizontal: 24,
    paddingTop: 40,
    paddingBottom: 32,
  },
  header: {
    alignItems: 'center',
    marginBottom: 28,
  },
  logoRing: {
    width: 72,
    height: 72,
    borderRadius: 36,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 12,
    borderWidth: 1,
    borderColor: C.primary + '40',
  },
  appName: {
    fontSize: 26,
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
  card: {
    backgroundColor: C.bgCard,
    borderRadius: 20,
    padding: 24,
    borderWidth: 1,
    borderColor: C.border,
  },
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
  fieldGroup: {
    marginBottom: 16,
  },
  label: {
    fontSize: 13,
    fontWeight: '600',
    color: C.textSecondary,
    marginBottom: 8,
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
    height: '100%',
  },
  eyeBtn: {
    padding: 4,
  },
  roleContainer: {
    flexDirection: 'row',
    gap: 12,
  },
  roleButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    backgroundColor: C.inputBg,
    borderWidth: 1,
    borderColor: C.border,
    borderRadius: 12,
    height: 50,
  },
  roleButtonActive: {
    backgroundColor: C.primary,
    borderColor: C.primary,
  },
  roleButtonText: {
    color: C.textSecondary,
    fontSize: 14,
    fontWeight: '600',
  },
  roleButtonTextActive: {
    color: '#000',
    fontWeight: '700',
  },
  btnContainer: {
    marginTop: 8,
    borderRadius: 14,
    overflow: 'hidden',
  },
  btn: {
    height: 54,
    alignItems: 'center',
    justifyContent: 'center',
  },
  btnInner: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  btnText: {
    color: '#000',
    fontSize: 16,
    fontWeight: '700',
  },
  footer: {
    alignItems: 'center',
    marginTop: 24,
  },
  signInLink: {
    color: C.textSecondary,
    fontSize: 14,
  },
});
