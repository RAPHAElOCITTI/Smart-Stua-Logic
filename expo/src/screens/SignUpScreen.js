/**
 * Smart-Stua Mobile — SignUpScreen.js
 * =====================================
 * Registers a new user against POST /api/auth/register/ on the Django backend.
 * On success, shows an Alert dialog then navigates back to the Login screen.
 *
 * Fields: Full Name, Phone Number, Email (optional), Password, Role selector.
 * Role choices: 'farmer' | 'store_manager' (matches backend UserRole enum).
 *
 * Navigation: after successful registration → navigation.navigate('Login')
 * (user must log in with their new credentials — no auto-login to keep auth
 * flow simple and explicit).
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
  Alert,
  Dimensions,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { register } from '../api';

// ─── Design Tokens (identical to LoginScreen and Dashboard) ───────────────────
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

// ─── Role Options ─────────────────────────────────────────────────────────────
const ROLES = [
  { value: 'farmer', label: 'Farmer', icon: 'leaf-outline' },
  { value: 'store_manager', label: 'Store Manager', icon: 'business-outline' },
];

export default function SignUpScreen({ navigation }) {
  // ─── Form State ─────────────────────────────────────────────────────────────
  const [fullName, setFullName] = useState('');
  const [phoneNumber, setPhoneNumber] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('farmer');
  const [showPassword, setShowPassword] = useState(false);

  // ─── UI State ────────────────────────────────────────────────────────────────
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [focusedField, setFocusedField] = useState(null);

  // ─── Focus Refs (keyboard "Next" chaining) ────────────────────────────────────
  const phoneRef = useRef(null);
  const emailRef = useRef(null);
  const passwordRef = useRef(null);

  // ─── Register Handler ─────────────────────────────────────────────────────────
  const handleRegister = async () => {
    Keyboard.dismiss();

    // ── Client-side validation ────────────────────────────────────────────────
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
      /**
       * POST /api/auth/register/
       * Body: { full_name, phone_number, email?, password, role }
       * Success 201: user object
       * Error 400:  { "phone_number": ["This field must be unique."], ... }
       */
      const payload = {
        full_name: fullName.trim(),
        phone_number: phoneNumber.trim(),
        password,
        role,
      };
      // Only include email if provided (it's optional on the backend)
      if (email.trim()) {
        payload.email = email.trim().toLowerCase();
      }

      await register(payload);

      // Success — show confirmation then route to Login
      Alert.alert(
        'Registration Successful',
        `Welcome, ${fullName.split(' ')[0]}! Your account has been created.\n\nPlease sign in with your new credentials.`,
        [
          {
            text: 'Sign In',
            onPress: () => navigation.navigate('Login'),
          },
        ],
        { cancelable: false }
      );

    } catch (err) {
      // ── DRF field-level error extraction ─────────────────────────────────────
      // DRF returns { "field": ["message 1", ...] } on validation errors
      const responseData = err?.response?.data;

      if (responseData && typeof responseData === 'object') {
        const messages = [];
        Object.entries(responseData).forEach(([field, msgs]) => {
          const fieldLabel = field === 'non_field_errors'
            ? ''
            : field.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) + ': ';
          const msgText = Array.isArray(msgs) ? msgs.join(' ') : String(msgs);
          messages.push(`${fieldLabel}${msgText}`);
        });
        setError(messages.join('\n'));
      } else if (err?.message?.includes('Network') || err?.message?.includes('network')) {
        setError('Cannot reach the server. Check your Wi-Fi and ensure the backend is running.');
      } else {
        setError(err?.message || 'Registration failed. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  // ─── Helpers ─────────────────────────────────────────────────────────────────
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
                  <Ionicons name="person-add" size={32} color={C.primary} />
                </LinearGradient>

                <Text style={styles.appName}>Create Account</Text>
                <Text style={styles.tagline}>Smart-Stua Monitoring Network</Text>
              </View>

              {/* ── Card ── */}
              <View style={styles.card}>
                <Text style={styles.cardTitle}>Register</Text>
                <Text style={styles.cardSubtitle}>
                  Join the Smart-Stua platform to monitor your grain storage
                </Text>

                {/* ── Error Banner ── */}
                {!!error && (
                  <View style={styles.errorBanner}>
                    <Ionicons name="alert-circle" size={16} color={C.danger} />
                    <Text style={styles.errorText}>{error}</Text>
                  </View>
                )}

                {/* ── Full Name ── */}
                <View style={styles.fieldGroup}>
                  <Text style={styles.label}>Full Name</Text>
                  <View style={inputStyle('name')}>
                    <Ionicons name="person-outline" size={18} color={iconColor('name')} style={styles.inputIcon} />
                    <TextInput
                      style={styles.input}
                      placeholder="Edwin Ocaya"
                      placeholderTextColor={C.textSecondary}
                      value={fullName}
                      onChangeText={text => { setFullName(text); if (error) setError(''); }}
                      onFocus={() => setFocusedField('name')}
                      onBlur={() => setFocusedField(null)}
                      autoCapitalize="words"
                      autoCorrect={false}
                      returnKeyType="next"
                      onSubmitEditing={() => phoneRef.current?.focus()}
                      blurOnSubmit={false}
                      editable={!loading}
                      testID="input-fullname"
                    />
                  </View>
                </View>

                {/* ── Phone Number ── */}
                <View style={styles.fieldGroup}>
                  <Text style={styles.label}>Phone Number</Text>
                  <View style={inputStyle('phone')}>
                    <Ionicons name="call-outline" size={18} color={iconColor('phone')} style={styles.inputIcon} />
                    <TextInput
                      ref={phoneRef}
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
                      onSubmitEditing={() => emailRef.current?.focus()}
                      blurOnSubmit={false}
                      editable={!loading}
                      testID="input-phone"
                    />
                  </View>
                </View>

                {/* ── Email (optional) ── */}
                <View style={styles.fieldGroup}>
                  <Text style={styles.label}>
                    Email Address{' '}
                    <Text style={styles.optionalTag}>(optional)</Text>
                  </Text>
                  <View style={inputStyle('email')}>
                    <Ionicons name="mail-outline" size={18} color={iconColor('email')} style={styles.inputIcon} />
                    <TextInput
                      ref={emailRef}
                      style={styles.input}
                      placeholder="you@example.com"
                      placeholderTextColor={C.textSecondary}
                      value={email}
                      onChangeText={text => { setEmail(text); if (error) setError(''); }}
                      onFocus={() => setFocusedField('email')}
                      onBlur={() => setFocusedField(null)}
                      keyboardType="email-address"
                      autoCapitalize="none"
                      autoCorrect={false}
                      returnKeyType="next"
                      onSubmitEditing={() => passwordRef.current?.focus()}
                      blurOnSubmit={false}
                      editable={!loading}
                      testID="input-email"
                    />
                  </View>
                </View>

                {/* ── Password ── */}
                <View style={styles.fieldGroup}>
                  <Text style={styles.label}>Password</Text>
                  <View style={inputStyle('password')}>
                    <Ionicons name="lock-closed-outline" size={18} color={iconColor('password')} style={styles.inputIcon} />
                    <TextInput
                      ref={passwordRef}
                      style={[styles.input, { flex: 1 }]}
                      placeholder="Min. 8 characters"
                      placeholderTextColor={C.textSecondary}
                      value={password}
                      onChangeText={text => { setPassword(text); if (error) setError(''); }}
                      onFocus={() => setFocusedField('password')}
                      onBlur={() => setFocusedField(null)}
                      secureTextEntry={!showPassword}
                      autoCapitalize="none"
                      autoCorrect={false}
                      returnKeyType="done"
                      onSubmitEditing={handleRegister}
                      editable={!loading}
                      testID="input-password"
                    />
                    <TouchableOpacity
                      onPress={() => setShowPassword(v => !v)}
                      style={styles.eyeBtn}
                      hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                      activeOpacity={0.7}
                    >
                      <Ionicons name={showPassword ? 'eye-off-outline' : 'eye-outline'} size={18} color={C.textSecondary} />
                    </TouchableOpacity>
                  </View>
                </View>

                {/* ── Role Selector ── */}
                <View style={styles.fieldGroup}>
                  <Text style={styles.label}>Role</Text>
                  <View style={styles.roleRow}>
                    {ROLES.map(({ value, label, icon }) => {
                      const isActive = role === value;
                      return (
                        <TouchableOpacity
                          key={value}
                          style={[styles.roleBtn, isActive && styles.roleBtnActive]}
                          onPress={() => setRole(value)}
                          disabled={loading}
                          activeOpacity={0.8}
                          testID={`role-${value}`}
                        >
                          <Ionicons name={icon} size={18} color={isActive ? '#000' : C.textSecondary} style={{ marginBottom: 2 }} />
                          <Text style={[styles.roleBtnText, isActive && styles.roleBtnTextActive]}>{label}</Text>
                        </TouchableOpacity>
                      );
                    })}
                  </View>
                </View>

                {/* ── Submit Button ── */}
                <TouchableOpacity onPress={handleRegister} disabled={loading} activeOpacity={0.85} style={styles.btnContainer} testID="btn-register">
                  <LinearGradient colors={loading ? ['#1E3A2F', '#1E3A2F'] : [C.primary, C.primaryDark]} style={styles.btn} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }}>
                    {loading ? (
                      <View style={styles.btnInner}>
                        <ActivityIndicator size="small" color={C.primary} />
                        <Text style={[styles.btnText, { color: C.primary, marginLeft: 8 }]}>Creating Account…</Text>
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

              {/* ── Footer ── */}
              <View style={styles.footer}>
                <TouchableOpacity onPress={() => { Keyboard.dismiss(); navigation.navigate('Login'); }} activeOpacity={0.7}>
                  <Text style={styles.signInLink}>
                    Already have an account?{' '}
                    <Text style={{ color: C.primary, fontWeight: '700' }}>Sign In</Text>
                  </Text>
                </TouchableOpacity>
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
                  <Ionicons name="person-add" size={32} color={C.primary} />
                </LinearGradient>

                <Text style={styles.appName}>Create Account</Text>
                <Text style={styles.tagline}>Smart-Stua Monitoring Network</Text>
              </View>

              {/* ── Card ── */}
              <View style={styles.card}>
                <Text style={styles.cardTitle}>Register</Text>
                <Text style={styles.cardSubtitle}>
                  Join the Smart-Stua platform to monitor your grain storage
                </Text>

                {/* ── Error Banner ── */}
                {!!error && (
                  <View style={styles.errorBanner}>
                    <Ionicons name="alert-circle" size={16} color={C.danger} />
                    <Text style={styles.errorText}>{error}</Text>
                  </View>
                )}

                {/* ── Full Name ── */}
                <View style={styles.fieldGroup}>
                  <Text style={styles.label}>Full Name</Text>
                  <View style={inputStyle('name')}>
                    <Ionicons name="person-outline" size={18} color={iconColor('name')} style={styles.inputIcon} />
                    <TextInput
                      style={styles.input}
                      placeholder="Edwin Ocaya"
                      placeholderTextColor={C.textSecondary}
                      value={fullName}
                      onChangeText={text => { setFullName(text); if (error) setError(''); }}
                      onFocus={() => setFocusedField('name')}
                      onBlur={() => setFocusedField(null)}
                      autoCapitalize="words"
                      autoCorrect={false}
                      returnKeyType="next"
                      onSubmitEditing={() => phoneRef.current?.focus()}
                      blurOnSubmit={false}
                      editable={!loading}
                      testID="input-fullname"
                    />
                  </View>
                </View>

                {/* ── Phone Number ── */}
                <View style={styles.fieldGroup}>
                  <Text style={styles.label}>Phone Number</Text>
                  <View style={inputStyle('phone')}>
                    <Ionicons name="call-outline" size={18} color={iconColor('phone')} style={styles.inputIcon} />
                    <TextInput
                      ref={phoneRef}
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
                      onSubmitEditing={() => emailRef.current?.focus()}
                      blurOnSubmit={false}
                      editable={!loading}
                      testID="input-phone"
                    />
                  </View>
                </View>

                {/* ── Email (optional) ── */}
                <View style={styles.fieldGroup}>
                  <Text style={styles.label}>
                    Email Address{' '}
                    <Text style={styles.optionalTag}>(optional)</Text>
                  </Text>
                  <View style={inputStyle('email')}>
                    <Ionicons name="mail-outline" size={18} color={iconColor('email')} style={styles.inputIcon} />
                    <TextInput
                      ref={emailRef}
                      style={styles.input}
                      placeholder="you@example.com"
                      placeholderTextColor={C.textSecondary}
                      value={email}
                      onChangeText={text => { setEmail(text); if (error) setError(''); }}
                      onFocus={() => setFocusedField('email')}
                      onBlur={() => setFocusedField(null)}
                      keyboardType="email-address"
                      autoCapitalize="none"
                      autoCorrect={false}
                      returnKeyType="next"
                      onSubmitEditing={() => passwordRef.current?.focus()}
                      blurOnSubmit={false}
                      editable={!loading}
                      testID="input-email"
                    />
                  </View>
                </View>

                {/* ── Password ── */}
                <View style={styles.fieldGroup}>
                  <Text style={styles.label}>Password</Text>
                  <View style={inputStyle('password')}>
                    <Ionicons name="lock-closed-outline" size={18} color={iconColor('password')} style={styles.inputIcon} />
                    <TextInput
                      ref={passwordRef}
                      style={[styles.input, { flex: 1 }]}
                      placeholder="Min. 8 characters"
                      placeholderTextColor={C.textSecondary}
                      value={password}
                      onChangeText={text => { setPassword(text); if (error) setError(''); }}
                      onFocus={() => setFocusedField('password')}
                      onBlur={() => setFocusedField(null)}
                      secureTextEntry={!showPassword}
                      autoCapitalize="none"
                      autoCorrect={false}
                      returnKeyType="done"
                      onSubmitEditing={handleRegister}
                      editable={!loading}
                      testID="input-password"
                    />
                    <TouchableOpacity
                      onPress={() => setShowPassword(v => !v)}
                      style={styles.eyeBtn}
                      hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                      activeOpacity={0.7}
                    >
                      <Ionicons name={showPassword ? 'eye-off-outline' : 'eye-outline'} size={18} color={C.textSecondary} />
                    </TouchableOpacity>
                  </View>
                </View>

                {/* ── Role Selector ── */}
                <View style={styles.fieldGroup}>
                  <Text style={styles.label}>Role</Text>
                  <View style={styles.roleRow}>
                    {ROLES.map(({ value, label, icon }) => {
                      const isActive = role === value;
                      return (
                        <TouchableOpacity
                          key={value}
                          style={[styles.roleBtn, isActive && styles.roleBtnActive]}
                          onPress={() => setRole(value)}
                          disabled={loading}
                          activeOpacity={0.8}
                          testID={`role-${value}`}
                        >
                          <Ionicons name={icon} size={18} color={isActive ? '#000' : C.textSecondary} style={{ marginBottom: 2 }} />
                          <Text style={[styles.roleBtnText, isActive && styles.roleBtnTextActive]}>{label}</Text>
                        </TouchableOpacity>
                      );
                    })}
                  </View>
                </View>

                {/* ── Submit Button ── */}
                <TouchableOpacity onPress={handleRegister} disabled={loading} activeOpacity={0.85} style={styles.btnContainer} testID="btn-register">
                  <LinearGradient colors={loading ? ['#1E3A2F', '#1E3A2F'] : [C.primary, C.primaryDark]} style={styles.btn} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }}>
                    {loading ? (
                      <View style={styles.btnInner}>
                        <ActivityIndicator size="small" color={C.primary} />
                        <Text style={[styles.btnText, { color: C.primary, marginLeft: 8 }]}>Creating Account…</Text>
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

              {/* ── Footer ── */}
              <View style={styles.footer}>
                <TouchableOpacity onPress={() => { Keyboard.dismiss(); navigation.navigate('Login'); }} activeOpacity={0.7}>
                  <Text style={styles.signInLink}>
                    Already have an account?{' '}
                    <Text style={{ color: C.primary, fontWeight: '700' }}>Sign In</Text>
                  </Text>
                </TouchableOpacity>
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
    paddingTop: 40,
    paddingBottom: 32,
  },

  // Header
  header: {
    alignItems: 'center',
    marginBottom: 30,
  },
  logoRing: {
    width: 80,
    height: 80,
    borderRadius: 40,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
    borderWidth: 1,
    borderColor: C.primary + '40',
  },
  appName: {
    fontSize: 26,
    fontWeight: '800',
    color: C.textPrimary,
    letterSpacing: 0.3,
  },
  tagline: {
    fontSize: 13,
    color: C.textSecondary,
    marginTop: 4,
    letterSpacing: 0.2,
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
    alignItems: 'flex-start',
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
  optionalTag: {
    fontWeight: '400',
    fontSize: 11,
    color: C.textSecondary,
    fontStyle: 'italic',
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

  // Role Selector
  roleRow: {
    flexDirection: 'row',
    gap: 12,
  },
  roleBtn: {
    flex: 1,
    height: 50,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: C.border,
    backgroundColor: C.inputBg,
    flexDirection: 'row',
    gap: 6,
  },
  roleBtnActive: {
    backgroundColor: C.primary,
    borderColor: C.primary,
  },
  roleBtnText: {
    color: C.textSecondary,
    fontSize: 13,
    fontWeight: '600',
  },
  roleBtnTextActive: {
    color: '#000',
    fontWeight: '700',
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
    marginTop: 24,
  },
  signInLink: {
    color: C.textSecondary,
    fontSize: 14,
  },
});
