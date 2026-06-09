/**
 * Smart-Stua Mobile — Axios API Client
 * Handles all communication with the Django REST backend.
 * Includes 30-second auto-refresh polling for the dashboard.
 *
 * Token Storage Strategy:
 *  - expo-secure-store  → auth token (encrypted, tamper-resistant)
 *  - AsyncStorage       → non-sensitive prefs (server base URL)
 */

import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as SecureStore from 'expo-secure-store';

// ─── Base URL Configuration ───────────────────────────────────────────────────
const DEFAULT_BASE_URL = 'http://192.168.1.180:8000/api';
const BASE_URL_KEY     = '@smart_stua_base_url';   // AsyncStorage — not sensitive
export const SECURE_TOKEN_KEY = 'smart_stua_auth_token'; // SecureStore — encrypted

// Axios instance
const api = axios.create({
  baseURL: DEFAULT_BASE_URL,
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
});

// ─── Auth Token Interceptor ───────────────────────────────────────────────────
// Reads the encrypted auth token from SecureStore on every request.
// Falls back gracefully so unauthenticated public endpoints still work.
api.interceptors.request.use(async config => {
  try {
    const [baseUrl, token] = await Promise.all([
      AsyncStorage.getItem(BASE_URL_KEY),          // base URL — AsyncStorage OK
      SecureStore.getItemAsync(SECURE_TOKEN_KEY),  // auth token — encrypted
    ]);
    if (baseUrl) {
      if (baseUrl.includes('192.168.1.179')) {
        await AsyncStorage.removeItem(BASE_URL_KEY);
      } else {
        config.baseURL = baseUrl + '/api';
      }
    }
    if (token)   config.headers.Authorization = `Token ${token}`; // DRF Token auth
  } catch (_) {}
  return config;
});

// ─── Config Helpers ───────────────────────────────────────────────────────────
export const setBaseUrl = async url => {
  await AsyncStorage.setItem(BASE_URL_KEY, url);
};

export const getBaseUrl = async () => {
  return (await AsyncStorage.getItem(BASE_URL_KEY)) || DEFAULT_BASE_URL;
};

// Write auth token securely (called by LoginScreen after successful login)
export const setAuthToken = async token => {
  await SecureStore.setItemAsync(SECURE_TOKEN_KEY, token);
};

// Delete auth token on logout — SecureStore delete is `deleteItemAsync`
export const clearAuthToken = async () => {
  await SecureStore.deleteItemAsync(SECURE_TOKEN_KEY);
};

// ─── Auth ─────────────────────────────────────────────────────────────────────
export const login = async credentials => {
  const response = await api.post('/auth/login/', credentials);
  return response.data;
};

export const register = async userData => {
  const response = await api.post('/auth/register/', userData);
  return response.data;
};

// ─── Dashboard ────────────────────────────────────────────────────────────────
export const fetchDashboardSummary = async () => {
  const response = await api.get('/dashboard/summary/');
  return response.data;
};

// ─── Devices ──────────────────────────────────────────────────────────────────
export const fetchDeviceList = async () => {
  const response = await api.get('/devices/');
  return response.data;
};

export const fetchDeviceReadings = async (nodeId, params = {}) => {
  const response = await api.get(`/devices/${nodeId}/readings/`, { params });
  return response.data;
};

export const fetchLatestReading = async nodeId => {
  const response = await api.get(`/devices/${nodeId}/latest/`);
  return response.data;
};

// ─── Alerts ───────────────────────────────────────────────────────────────────
export const fetchAlerts = async (params = {}) => {
  const response = await api.get('/alerts/', { params });
  return response.data;
};

export const acknowledgeAlert = async alertId => {
  const response = await api.patch(`/alerts/${alertId}/acknowledge/`);
  return response.data;
};

// ─── Thresholds ───────────────────────────────────────────────────────────────
export const fetchThresholds = async nodeIdentifier => {
  const response = await api.get(`/thresholds/${nodeIdentifier}/`);
  return response.data;
};

export const updateThresholds = async (nodeIdentifier, data) => {
  const response = await api.put(`/thresholds/${nodeIdentifier}/`, data);
  return response.data;
};

// ─── Dryer Control ────────────────────────────────────────────────────────────
export const sendDryerCommand = async (nodeId, action) => {
  const response = await api.post(`/devices/${nodeId}/dryer/`, { action });
  return response.data;
};

// ─── 30-Second Polling Manager ────────────────────────────────────────────────
let pollingInterval = null;

export const startPolling = (callback, intervalMs = 30000) => {
  stopPolling();
  callback(); // Immediate first call
  pollingInterval = setInterval(callback, intervalMs);
  return pollingInterval;
};

export const stopPolling = () => {
  if (pollingInterval) {
    clearInterval(pollingInterval);
    pollingInterval = null;
  }
};

// ─── Risk Utilities ───────────────────────────────────────────────────────────
export const getRiskColor = riskLevel => {
  switch (riskLevel) {
    case 'High':   return '#FF3B30';
    case 'Medium': return '#FF9500';
    case 'Low':    return '#34C759';
    default:       return '#8E8E93';
  }
};

export const getRiskIcon = riskLevel => {
  switch (riskLevel) {
    case 'High':   return 'alert-circle';
    case 'Medium': return 'warning';
    case 'Low':    return 'checkmark-circle';
    default:       return 'help-circle';
  }
};

export default api;
