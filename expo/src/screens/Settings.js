/**
 * Settings Screen
 * UC3: "Configure Alert Thresholds" + User profile + Server config
 *
 * Features:
 *   - Per-node threshold configuration (temp, humidity, risk duration)
 *   - Server URL configuration (stored in AsyncStorage)
 *   - About section with ARI algorithm info
 */

import React, { useState, useEffect } from 'react';
import {
  View, Text, ScrollView, TouchableOpacity, TextInput,
  StyleSheet, SafeAreaView, Alert, ActivityIndicator, useWindowDimensions,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { fetchDeviceList, fetchThresholds, updateThresholds, setBaseUrl, clearAuthToken } from '../api';

const C = {
  bg:      '#0A0F1E',
  card:    '#1A2340',
  border:  '#1E293B',
  text:    '#F0F4FF',
  subtext: '#8892A4',
  primary: '#00D26A',
  danger:  '#FF3B30',
  warning: '#FF9500',
  input:   '#0D1526',
};

export default function SettingsScreen() {
  const { width } = useWindowDimensions();
  const responsiveTitleSize = Math.min(Math.max(width * 0.065, 22), 34);
  const navigation = useNavigation();
  const [nodes, setNodes]               = useState([]);
  const [selectedNode, setSelectedNode] = useState(null);
  const [thresholds, setThresholds]     = useState(null);
  const [serverUrl, setServerUrl]       = useState('');
  const [saving, setSaving]             = useState(false);
  const [loadingThresh, setLoadingThresh] = useState(false);

  const [minTemp, setMinTemp]           = useState('');
  const [maxTemp, setMaxTemp]           = useState('');
  const [minHum, setMinHum]             = useState('');
  const [maxHum, setMaxHum]             = useState('');
  const [riskDuration, setRiskDuration] = useState('');

  useEffect(() => { loadInitial(); }, []);

  const loadInitial = async () => {
    try {
      const saved = await AsyncStorage.getItem('@smart_stua_base_url');
      if (saved) setServerUrl(saved);
      const data = await fetchDeviceList();
      const list = Array.isArray(data) ? data : [];
      setNodes(list);
      if (list.length > 0) selectNode(list[0]);
    } catch (err) {
      console.error('[Settings] Load failed:', err.message);
    }
  };

  const selectNode = async node => {
    setSelectedNode(node);
    setLoadingThresh(true);
    try {
      const t = await fetchThresholds(node.node_identifier);
      setThresholds(t);
      setMinTemp(String(t.min_temp));
      setMaxTemp(String(t.max_temp));
      setMinHum(String(t.min_humidity));
      setMaxHum(String(t.max_humidity));
      setRiskDuration(String(t.risk_duration));
    } catch (err) {
      console.error('[Settings] Threshold fetch failed:', err.message);
    } finally {
      setLoadingThresh(false);
    }
  };

  const saveThresholds = async () => {
    if (!selectedNode) return;
    setSaving(true);
    try {
      await updateThresholds(selectedNode.node_identifier, {
        min_temp:      parseFloat(minTemp),
        max_temp:      parseFloat(maxTemp),
        min_humidity:  parseFloat(minHum),
        max_humidity:  parseFloat(maxHum),
        risk_duration: parseInt(riskDuration, 10),
      });
      Alert.alert('Saved', `Thresholds updated for ${selectedNode.node_identifier}`);
    } catch (err) {
      Alert.alert('Error', 'Failed to save thresholds: ' + err.message);
    } finally {
      setSaving(false);
    }
  };

  const saveServerUrl = async () => {
    if (!serverUrl.startsWith('http')) {
      Alert.alert('Invalid URL', 'Must start with http:// or https://');
      return;
    }
    await setBaseUrl(serverUrl.replace(/\/$/, ''));
    Alert.alert('Saved', 'Server URL updated. Restart the app to apply.');
  };

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <View style={styles.header}>
          <Text style={[styles.title, { fontSize: responsiveTitleSize }]}>Settings</Text>
          <Text style={styles.subtitle}>Configure thresholds & connectivity</Text>
        </View>

        {/* Server Configuration */}
        <SectionHeader icon="cloud-outline" title="Server Configuration" />
        <View style={styles.card}>
          <Text style={styles.fieldLabel}>Django API URL</Text>
          <TextInput
            style={styles.input}
            value={serverUrl}
            onChangeText={setServerUrl}
            placeholder="http://your-server.com"
            placeholderTextColor={C.subtext}
            autoCapitalize="none"
            keyboardType="url"
          />
          <Text style={styles.hint}>URL of your Django backend (without /api/ suffix)</Text>
          <TouchableOpacity style={styles.saveBtn} onPress={saveServerUrl}>
            <Ionicons name="save-outline" size={16} color="#000" />
            <Text style={styles.saveBtnText}>Save URL</Text>
          </TouchableOpacity>
        </View>

        {/* Alert Thresholds */}
        <SectionHeader icon="thermometer-outline" title="Alert Thresholds" />

        {nodes.length > 0 && (
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.chipRow}>
            {nodes.map(n => (
              <TouchableOpacity
                key={n.node_id}
                style={[styles.chip, selectedNode?.node_id === n.node_id && styles.chipActive]}
                onPress={() => selectNode(n)}
              >
                <Text style={[styles.chipText, selectedNode?.node_id === n.node_id && styles.chipTextActive]}>
                  {n.node_identifier}
                </Text>
              </TouchableOpacity>
            ))}
          </ScrollView>
        )}

        {loadingThresh ? (
          <View style={[styles.card, styles.centered]}>
            <ActivityIndicator color={C.primary} />
          </View>
        ) : thresholds ? (
          <View style={styles.card}>
            <Text style={styles.nodeLabel}>{selectedNode?.location_label}</Text>
            <View style={styles.fieldRow}>
              <Field label="Min Temp (°C)"    value={minTemp}      onChangeText={setMinTemp}      color="#0A84FF" />
              <Field label="Max Temp (°C)"    value={maxTemp}      onChangeText={setMaxTemp}      color={C.danger} />
            </View>
            <View style={styles.fieldRow}>
              <Field label="Min Humidity (%)" value={minHum}       onChangeText={setMinHum}       color="#0A84FF" />
              <Field label="Max Humidity (%)" value={maxHum}       onChangeText={setMaxHum}       color={C.warning} />
            </View>
            <Field
              label="Risk Duration (hours)"
              value={riskDuration}
              onChangeText={setRiskDuration}
              color={C.warning}
              hint="Hours of sustained risk before dryer activates"
            />
            <TouchableOpacity
              style={[styles.saveBtn, saving && styles.saveBtnDisabled]}
              onPress={saveThresholds}
              disabled={saving}
            >
              {saving ? (
                <ActivityIndicator size="small" color="#000" />
              ) : (
                <>
                  <Ionicons name="checkmark-circle-outline" size={16} color="#000" />
                  <Text style={styles.saveBtnText}>Save Thresholds</Text>
                </>
              )}
            </TouchableOpacity>
          </View>
        ) : (
          <View style={styles.card}>
            <Text style={styles.noData}>No nodes available. Register a sensor node first.</Text>
          </View>
        )}

        {/* ARI Algorithm Info */}
        <SectionHeader icon="information-circle-outline" title="ARI Algorithm" />
        <View style={styles.card}>
          <Text style={styles.fieldLabel}>Aflatoxin Risk Index (0–100)</Text>
          <Text style={styles.body}>
            Quantifies aflatoxin contamination risk based on Aspergillus flavus growth parameters:
          </Text>
          <InfoRow icon="thermometer" color="#FF9500" text="Temperature: Gaussian peak at 30°C" />
          <InfoRow icon="water" color="#0A84FF" text="Humidity: Sigmoid above 75% RH threshold" />
          <InfoRow icon="time-outline" color={C.primary} text="Duration: Logarithmic accumulation of exposure" />
          <View style={styles.riskLegend}>
            <LegendItem color={C.primary} label="Low"    range="0–30"   action="Normal — log reading" />
            <LegendItem color={C.warning} label="Medium" range="31–70"  action="Warning — advisory SMS" />
            <LegendItem color={C.danger}  label="High"   range="71–100" action="Critical — dryer + SMS" />
          </View>
        </View>

        {/* About */}
        <SectionHeader icon="leaf-outline" title="About Smart-Stua" />
        <View style={styles.card}>
          <Text style={styles.fieldLabel}>v1.0 — Gulu District, Uganda</Text>
          <Text style={[styles.body, { marginTop: 4 }]}>
            IoT aflatoxin prevention for grain storage facilities.
          </Text>
          <Text style={[styles.body, { marginTop: 8, color: C.subtext }]}>
            Hardware: ESP32 + DHT22{'\n'}
            Connectivity: WiFi (primary) → GSM SIM800L (fallback){'\n'}
            Backend: Django + SQLite{'\n'}
            Mobile: React Native (Expo)
          </Text>
        </View>

        {/* ── Logout ── */}
        <SectionHeader icon="log-out-outline" title="Account" />
        <View style={styles.card}>
          <TouchableOpacity
            style={styles.logoutBtn}
            onPress={() => {
              Alert.alert(
                'Sign Out',
                'Are you sure you want to log out?',
                [
                  { text: 'Cancel', style: 'cancel' },
                  {
                    text: 'Sign Out',
                    style: 'destructive',
                    onPress: async () => {
                      // Clear encrypted auth token from SecureStore
                      await clearAuthToken();
                      // Reset navigator stack back to Login
                      navigation.getParent()?.reset({
                        index: 0,
                        routes: [{ name: 'Login' }],
                      });
                    },
                  },
                ]
              );
            }}
          >
            <Ionicons name="log-out-outline" size={18} color={C.danger} />
            <Text style={styles.logoutText}>Sign Out</Text>
          </TouchableOpacity>
        </View>

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

function SectionHeader({ icon, title }) {
  return (
    <View style={styles.sectionHeader}>
      <Ionicons name={icon} size={18} color="#8892A4" />
      <Text style={styles.sectionTitle}>{title}</Text>
    </View>
  );
}

function Field({ label, value, onChangeText, color, hint }) {
  return (
    <View style={styles.field}>
      <Text style={[styles.fieldLabel, color && { color }]}>{label}</Text>
      <TextInput
        style={styles.input}
        value={value}
        onChangeText={onChangeText}
        keyboardType="numeric"
        placeholderTextColor="#4A5568"
      />
      {hint ? <Text style={styles.hint}>{hint}</Text> : null}
    </View>
  );
}

function InfoRow({ icon, color, text }) {
  return (
    <View style={styles.infoRow}>
      <Ionicons name={icon} size={16} color={color} />
      <Text style={styles.infoText}>{text}</Text>
    </View>
  );
}

function LegendItem({ color, label, range, action }) {
  return (
    <View style={styles.legendItem}>
      <View style={[styles.legendDot, { backgroundColor: color }]} />
      <Text style={[styles.legendLabel, { color }]}>{label}</Text>
      <Text style={styles.legendRange}>{range}</Text>
      <Text style={styles.legendAction}>{action}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container:      { flex: 1, backgroundColor: C.bg },
  scroll:         { padding: 16 },
  centered:       { alignItems: 'center', justifyContent: 'center', minHeight: 80 },
  header:         { marginBottom: 20 },
  title:          { fontSize: 26, fontWeight: '800', color: C.text },
  subtitle:       { fontSize: 13, color: C.subtext, marginTop: 2 },
  sectionHeader:  { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 16, marginBottom: 8 },
  sectionTitle:   { fontSize: 13, fontWeight: '700', color: C.subtext, letterSpacing: 1, textTransform: 'uppercase' },
  card:           { backgroundColor: C.card, borderRadius: 16, padding: 16, marginBottom: 4, borderWidth: 1, borderColor: C.border, gap: 10 },
  nodeLabel:      { color: C.subtext, fontSize: 13, marginBottom: 4 },
  fieldRow:       { flexDirection: 'row', gap: 12 },
  field:          { flex: 1, gap: 4 },
  fieldLabel:     { color: C.text, fontSize: 13, fontWeight: '600' },
  input:          { backgroundColor: C.input, borderRadius: 10, borderWidth: 1, borderColor: C.border, color: C.text, padding: 12, fontSize: 15 },
  hint:           { color: C.subtext, fontSize: 11, lineHeight: 15 },
  noData:         { color: C.subtext, fontSize: 14, textAlign: 'center', paddingVertical: 16 },
  saveBtn:        { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: C.primary, borderRadius: 12, paddingVertical: 14, marginTop: 4 },
  saveBtnDisabled:{ opacity: 0.6 },
  saveBtnText:    { color: '#000', fontSize: 15, fontWeight: '800' },
  chipRow:        { marginBottom: 8 },
  chip:           { paddingVertical: 6, paddingHorizontal: 14, borderRadius: 20, backgroundColor: C.card, borderWidth: 1, borderColor: C.border, marginRight: 8 },
  chipActive:     { borderColor: C.primary, backgroundColor: '#0A2B1E' },
  chipText:       { color: C.subtext, fontSize: 13, fontWeight: '600' },
  chipTextActive: { color: C.primary },
  body:           { color: C.subtext, fontSize: 13, lineHeight: 20 },
  infoRow:        { flexDirection: 'row', alignItems: 'flex-start', gap: 8, marginTop: 4 },
  infoText:       { color: C.text, fontSize: 13, flex: 1, lineHeight: 18 },
  riskLegend:     { marginTop: 8, gap: 6 },
  legendItem:     { flexDirection: 'row', alignItems: 'center', gap: 8 },
  legendDot:      { width: 10, height: 10, borderRadius: 5 },
  legendLabel:    { fontSize: 13, fontWeight: '700', width: 60 },
  legendRange:    { color: C.subtext, fontSize: 12, width: 50 },
  legendAction:   { color: C.subtext, fontSize: 12, flex: 1 },
  logoutBtn:      { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: C.danger + '1A', borderWidth: 1, borderColor: C.danger + '40', borderRadius: 12, paddingVertical: 14 },
  logoutText:     { color: C.danger, fontSize: 15, fontWeight: '700' },
});
