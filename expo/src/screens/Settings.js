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
  Clipboard,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import {
  fetchDeviceList,
  fetchThresholds,
  updateThresholds,
  setBaseUrl,
  clearAuthToken,
  registerDevice,
  updateDevice,
  deleteDevice,
  rotateApiKey,
  fetchDeviceDetail
} from '../api';

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

  // Node management states
  const [registerFormVisible, setRegisterFormVisible] = useState(false);
  const [newNodeIdentifier, setNewNodeIdentifier] = useState('');
  const [newLocationLabel, setNewLocationLabel] = useState('');
  const [newMacAddress, setNewMacAddress] = useState('');
  const [newNotes, setNewNotes] = useState('');
  const [provisioningData, setProvisioningData] = useState(null);
  const [editingNode, setEditingNode] = useState(null);
  const [isRefreshingNodes, setIsRefreshingNodes] = useState(false);

  const refreshNodes = async () => {
    setIsRefreshingNodes(true);
    try {
      const data = await fetchDeviceList();
      const list = Array.isArray(data) ? data : [];
      setNodes(list);
    } catch (err) {
      console.error('[Settings] Refresh nodes failed:', err.message);
    } finally {
      setIsRefreshingNodes(false);
    }
  };

  const handleRegisterNode = async () => {
    if (!newNodeIdentifier || !newLocationLabel) {
      Alert.alert('Error', 'Node Identifier and Location Label are required.');
      return;
    }
    setSaving(true);
    try {
      const payload = {
        node_identifier: newNodeIdentifier,
        location_label: newLocationLabel,
        mac_address: newMacAddress,
        notes: newNotes,
      };
      const response = await registerDevice(payload);
      setProvisioningData(response);
      setNewNodeIdentifier('');
      setNewLocationLabel('');
      setNewMacAddress('');
      setNewNotes('');
      setRegisterFormVisible(false);
      await refreshNodes();
      Alert.alert('Success', 'Node registered successfully!');
    } catch (err) {
      Alert.alert('Registration Error', err.response?.data ? JSON.stringify(err.response.data) : err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleUpdateNode = async (node) => {
    setSaving(true);
    try {
      await updateDevice(node.node_id, {
        location_label: node.location_label,
        mac_address: node.mac_address,
        notes: node.notes,
        status: node.status,
      });
      setEditingNode(null);
      await refreshNodes();
      Alert.alert('Success', 'Node updated successfully!');
    } catch (err) {
      Alert.alert('Update Error', err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteNode = (node) => {
    Alert.alert(
      'Deactivate Node',
      `Are you sure you want to deactivate ${node.node_identifier}? It will be soft-deleted (historical data will remain).`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Deactivate',
          style: 'destructive',
          onPress: async () => {
            try {
              await deleteDevice(node.node_id);
              await refreshNodes();
              Alert.alert('Deactivated', `Node ${node.node_identifier} is now inactive.`);
            } catch (err) {
              Alert.alert('Deactivation Error', err.message);
            }
          }
        }
      ]
    );
  };

  const handleRotateKey = (node) => {
    Alert.alert(
      'Rotate API Key',
      `Warning: Rotated API keys cannot be recovered. You must update your hardware firmware config immediately. Continue?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Rotate',
          style: 'destructive',
          onPress: async () => {
            try {
              const res = await rotateApiKey(node.node_id);
              setProvisioningData(res);
              Alert.alert('Rotated', 'New API Key generated successfully!');
            } catch (err) {
              Alert.alert('Rotation Error', err.message);
            }
          }
        }
      ]
    );
  };

  const copyToClipboard = (text) => {
    Clipboard.setString(text);
    Alert.alert('Copied', 'Config copied to clipboard!');
  };

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

        {/* Node Registration & Management (Feature 2) */}
        <SectionHeader icon="hardware-chip-outline" title="Node Management" />
        <View style={styles.card}>
          <View style={styles.nodeHeaderRow}>
            <Text style={styles.fieldLabel}>Registered Nodes</Text>
            <TouchableOpacity onPress={refreshNodes} style={styles.iconBtn}>
              <Ionicons name="refresh-outline" size={16} color={C.primary} />
            </TouchableOpacity>
          </View>

          {isRefreshingNodes ? (
            <ActivityIndicator color={C.primary} style={{ marginVertical: 12 }} />
          ) : nodes.length === 0 ? (
            <Text style={styles.noData}>No devices registered. Add one below.</Text>
          ) : (
            nodes.map(node => (
              <View key={node.node_id} style={styles.nodeListItem}>
                <View style={styles.nodeListInfo}>
                  <View style={styles.nodeNameRow}>
                    <View style={[styles.statusDot, { backgroundColor: node.is_online ? '#00D26A' : '#FF3B30' }]} />
                    <Text style={styles.nodeNameText}>{node.node_identifier}</Text>
                  </View>
                  <Text style={styles.nodeLocText}>{node.location_label || 'No Location'}</Text>
                </View>
                <View style={styles.nodeActionRow}>
                  <TouchableOpacity onPress={() => setEditingNode(node)} style={styles.actionBtn}>
                    <Ionicons name="create-outline" size={18} color="#0A84FF" />
                  </TouchableOpacity>
                  <TouchableOpacity onPress={() => handleRotateKey(node)} style={styles.actionBtn}>
                    <Ionicons name="key-outline" size={18} color="#FF9500" />
                  </TouchableOpacity>
                  <TouchableOpacity onPress={() => handleDeleteNode(node)} style={styles.actionBtn}>
                    <Ionicons name="trash-outline" size={18} color="#FF3B30" />
                  </TouchableOpacity>
                </View>
              </View>
            ))
          )}

          {/* Edit Node Section */}
          {editingNode && (
            <View style={styles.editContainer}>
              <Text style={[styles.fieldLabel, { marginTop: 12 }]}>Edit Node: {editingNode.node_identifier}</Text>
              <TextInput
                style={styles.input}
                value={editingNode.location_label}
                onChangeText={(text) => setEditingNode({ ...editingNode, location_label: text })}
                placeholder="Location Label"
                placeholderTextColor={C.subtext}
              />
              <TextInput
                style={styles.input}
                value={editingNode.mac_address}
                onChangeText={(text) => setEditingNode({ ...editingNode, mac_address: text })}
                placeholder="MAC Address (Optional)"
                placeholderTextColor={C.subtext}
              />
              <TextInput
                style={styles.input}
                value={editingNode.notes}
                onChangeText={(text) => setEditingNode({ ...editingNode, notes: text })}
                placeholder="Notes (Optional)"
                placeholderTextColor={C.subtext}
              />
              <View style={styles.btnRow}>
                <TouchableOpacity style={[styles.saveBtn, { flex: 1, backgroundColor: '#1E293B', borderColor: '#4A5568' }]} onPress={() => setEditingNode(null)}>
                  <Text style={[styles.saveBtnText, { color: C.text }]}>Cancel</Text>
                </TouchableOpacity>
                <TouchableOpacity style={[styles.saveBtn, { flex: 1 }]} onPress={() => handleUpdateNode(editingNode)}>
                  <Text style={styles.saveBtnText}>Save</Text>
                </TouchableOpacity>
              </View>
            </View>
          )}

          {/* Toggle Register Form Button */}
          {!registerFormVisible && !editingNode && (
            <TouchableOpacity style={styles.registerToggleBtn} onPress={() => setRegisterFormVisible(true)}>
              <Ionicons name="add-circle-outline" size={18} color="#000" />
              <Text style={styles.registerToggleBtnText}>Register New Node</Text>
            </TouchableOpacity>
          )}

          {/* Registration Form */}
          {registerFormVisible && (
            <View style={styles.registerForm}>
              <Text style={[styles.fieldLabel, { marginTop: 12 }]}>Register New Node</Text>
              <TextInput
                style={styles.input}
                value={newNodeIdentifier}
                onChangeText={setNewNodeIdentifier}
                placeholder="Node ID (e.g. NODE_003)"
                placeholderTextColor={C.subtext}
                autoCapitalize="characters"
              />
              <TextInput
                style={styles.input}
                value={newLocationLabel}
                onChangeText={setNewLocationLabel}
                placeholder="Location (e.g. Silo B)"
                placeholderTextColor={C.subtext}
              />
              <TextInput
                style={styles.input}
                value={newMacAddress}
                onChangeText={setNewMacAddress}
                placeholder="MAC Address (Optional)"
                placeholderTextColor={C.subtext}
              />
              <TextInput
                style={styles.input}
                value={newNotes}
                onChangeText={setNewNotes}
                placeholder="Notes (Optional)"
                placeholderTextColor={C.subtext}
              />
              <View style={styles.btnRow}>
                <TouchableOpacity style={[styles.saveBtn, { flex: 1, backgroundColor: '#1E293B', borderColor: '#4A5568' }]} onPress={() => setRegisterFormVisible(false)}>
                  <Text style={[styles.saveBtnText, { color: C.text }]}>Cancel</Text>
                </TouchableOpacity>
                <TouchableOpacity style={[styles.saveBtn, { flex: 1 }]} onPress={handleRegisterNode}>
                  <Text style={styles.saveBtnText}>Register</Text>
                </TouchableOpacity>
              </View>
            </View>
          )}
        </View>

        {/* Provisioning Sheet (One-time pair info) */}
        {provisioningData && (
          <View style={styles.provisioningCard}>
            <View style={styles.provisioningHeader}>
              <Ionicons name="key" size={20} color={C.warning} />
              <Text style={styles.provisioningTitle}>Device Provisioning Key</Text>
            </View>
            <Text style={styles.provisioningWarning}>
              IMPORTANT: Copy this configuration. The API Key is generated dynamically and cannot be displayed again for security reasons.
            </Text>
            <View style={styles.keyBox}>
              <Text style={styles.keyTextLabel}>API Key:</Text>
              <Text style={styles.keyValue} selectable>{provisioningData.api_key}</Text>
            </View>
            {provisioningData.provisioning && (
              <View style={styles.configDetails}>
                <Text style={styles.configDetailText}><Text style={styles.bold}>MQTT Broker:</Text> {provisioningData.provisioning.mqtt_broker}</Text>
                <Text style={styles.configDetailText}><Text style={styles.bold}>MQTT Port:</Text> {provisioningData.provisioning.mqtt_port}</Text>
                <Text style={styles.configDetailText}><Text style={styles.bold}>MQTT Topic:</Text> {provisioningData.provisioning.mqtt_topic}</Text>
              </View>
            )}
            <TouchableOpacity style={styles.copyBtn} onPress={() => copyToClipboard(JSON.stringify(provisioningData, null, 2))}>
              <Ionicons name="copy-outline" size={16} color="#000" />
              <Text style={styles.copyBtnText}>Copy Config JSON</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.closeBtn} onPress={() => setProvisioningData(null)}>
              <Text style={styles.closeBtnText}>Done</Text>
            </TouchableOpacity>
          </View>
        )}

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
  
  // Node management styles
  nodeHeaderRow:  { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  iconBtn:        { padding: 4 },
  nodeListItem:   { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: C.border },
  nodeListInfo:   { flex: 1 },
  nodeNameRow:    { flexDirection: 'row', alignItems: 'center', gap: 6 },
  statusDot:      { width: 8, height: 8, borderRadius: 4 },
  nodeNameText:   { color: C.text, fontSize: 15, fontWeight: '700' },
  nodeLocText:    { color: C.subtext, fontSize: 12, marginTop: 2 },
  nodeActionRow:  { flexDirection: 'row', gap: 14 },
  actionBtn:      { padding: 4 },
  editContainer:  { gap: 8, paddingVertical: 8 },
  btnRow:         { flexDirection: 'row', gap: 10, marginTop: 8 },
  registerToggleBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: C.primary, borderRadius: 12, paddingVertical: 14, marginTop: 12 },
  registerToggleBtnText: { color: '#000', fontSize: 15, fontWeight: '800' },
  registerForm:   { gap: 8, paddingVertical: 8 },
  
  // Provisioning Sheet Styles
  provisioningCard: { backgroundColor: C.card, borderRadius: 16, padding: 16, marginTop: 16, borderWidth: 1, borderColor: C.warning, gap: 10 },
  provisioningHeader: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  provisioningTitle: { fontSize: 15, fontWeight: '700', color: C.text },
  provisioningWarning: { fontSize: 12, color: C.warning, lineHeight: 18 },
  keyBox:         { backgroundColor: C.input, padding: 12, borderRadius: 10, borderWidth: 1, borderColor: C.border, gap: 4 },
  keyTextLabel:   { fontSize: 11, color: C.subtext, textTransform: 'uppercase', fontWeight: '600' },
  keyValue:       { fontSize: 13, fontFamily: 'monospace', color: C.text, fontWeight: '700' },
  configDetails:  { gap: 4, marginVertical: 4 },
  configDetailText: { fontSize: 13, color: C.text },
  bold:           { fontWeight: '700', color: C.subtext },
  copyBtn:        { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: C.primary, borderRadius: 12, paddingVertical: 12 },
  copyBtnText:    { color: '#000', fontSize: 14, fontWeight: '700' },
  closeBtn:       { alignItems: 'center', justifyContent: 'center', backgroundColor: '#1E293B', borderRadius: 12, paddingVertical: 12, borderWidth: 1, borderColor: '#4A5568' },
  closeBtnText:   { color: C.text, fontSize: 14, fontWeight: '700' },
});
