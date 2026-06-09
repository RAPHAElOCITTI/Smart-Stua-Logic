/**
 * DeviceList Screen
 * Lists all registered sensor nodes with status badges, last reading,
 * and current ARI risk level. Tap to navigate to device-specific dashboard.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, FlatList, TouchableOpacity, StyleSheet,
  SafeAreaView, ActivityIndicator, RefreshControl, useWindowDimensions,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { fetchDeviceList } from '../api';
import { format } from 'date-fns';

const C = {
  bg:      '#0A0F1E',
  surface: '#141B2D',
  card:    '#1A2340',
  border:  '#1E293B',
  text:    '#F0F4FF',
  subtext: '#8892A4',
  primary: '#00D26A',
  danger:  '#FF3B30',
  warning: '#FF9500',
};

const STATUS_CONFIG = {
  active:      { color: C.primary, icon: 'radio-button-on',  label: 'Active' },
  inactive:    { color: C.danger,  icon: 'radio-button-off', label: 'Inactive' },
  maintenance: { color: C.warning, icon: 'construct',        label: 'Maintenance' },
};

const RISK_CONFIG = {
  High:   { color: C.danger,  bg: '#3A1A1A' },
  Medium: { color: C.warning, bg: '#2A1E0A' },
  Low:    { color: C.primary, bg: '#0A2B1E' },
};

export default function DeviceListScreen({ navigation }) {
  const { width } = useWindowDimensions();
  const responsiveTitleSize = Math.min(Math.max(width * 0.065, 22), 34);
  const [devices, setDevices]     = useState([]);
  const [loading, setLoading]     = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError]         = useState(null);

  const loadDevices = useCallback(async () => {
    try {
      const data = await fetchDeviceList();
      setDevices(Array.isArray(data) ? data : []);
      setError(null);
    } catch (err) {
      setError('Failed to load devices');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { loadDevices(); }, []);

  const onRefresh = () => { setRefreshing(true); loadDevices(); };

  const renderDevice = ({ item }) => {
    const statusCfg = STATUS_CONFIG[item.status] || STATUS_CONFIG.inactive;
    const riskCfg   = RISK_CONFIG[item.latest_ari?.risk_level] || RISK_CONFIG.Low;
    const ari       = item.latest_ari;

    return (
      <TouchableOpacity
        style={styles.card}
        activeOpacity={0.8}
        onPress={() => {
          // Navigate to device-specific dashboard view
          // In a real app, pass navigation params
        }}
      >
        {/* Top row */}
        <View style={styles.cardTop}>
          <View style={styles.nodeIdRow}>
            <Ionicons name="hardware-chip" size={20} color={C.primary} />
            <Text style={styles.nodeId}>{item.node_identifier}</Text>
          </View>
          <View style={[styles.statusBadge, { backgroundColor: `${statusCfg.color}22` }]}>
            <Ionicons name={statusCfg.icon} size={12} color={statusCfg.color} />
            <Text style={[styles.statusText, { color: statusCfg.color }]}>
              {statusCfg.label}
            </Text>
          </View>
        </View>

        {/* Location */}
        <View style={styles.locationRow}>
          <Ionicons name="location-outline" size={14} color={C.subtext} />
          <Text style={styles.locationText}>{item.location_label}</Text>
        </View>

        {/* Divider */}
        <View style={styles.divider} />

        {/* Readings Row */}
        <View style={styles.readingsRow}>
          {/* ARI Badge */}
          {ari ? (
            <View style={[styles.ariBadge, { backgroundColor: riskCfg.bg }]}>
              <Text style={[styles.ariLabel, { color: riskCfg.color }]}>
                ARI {ari.ari_value?.toFixed(1)}
              </Text>
              <Text style={[styles.ariRisk, { color: riskCfg.color }]}>
                {ari.risk_level}
              </Text>
            </View>
          ) : (
            <View style={styles.ariBadge}>
              <Text style={styles.noData}>No data</Text>
            </View>
          )}

          {/* Last reading time */}
          <View style={styles.lastReadingBlock}>
            <Text style={styles.lastReadingLabel}>Last reading</Text>
            <Text style={styles.lastReadingTime}>
              {item.last_reading_at
                ? format(new Date(item.last_reading_at), 'MMM dd HH:mm')
                : 'Never'}
            </Text>
          </View>

          <Ionicons name="chevron-forward" size={18} color={C.subtext} />
        </View>
      </TouchableOpacity>
    );
  };

  if (loading) {
    return (
      <SafeAreaView style={[styles.container, styles.centered]}>
        <ActivityIndicator size="large" color={C.primary} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={[styles.title, { fontSize: responsiveTitleSize }]}>Sensor Nodes</Text>
        <Text style={styles.subtitle}>{devices.length} registered</Text>
      </View>

      <FlatList
        data={devices}
        keyExtractor={item => String(item.node_id)}
        renderItem={renderDevice}
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.primary} />
        }
        ListEmptyComponent={
          <View style={styles.empty}>
            <Ionicons name="hardware-chip-outline" size={60} color={C.subtext} />
            <Text style={styles.emptyText}>No devices registered</Text>
          </View>
        }
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: C.bg },
  centered:  { alignItems: 'center', justifyContent: 'center' },
  header:    { padding: 20, paddingTop: 16 },
  title:     { fontSize: 26, fontWeight: '800', color: C.text },
  subtitle:  { fontSize: 13, color: C.subtext, marginTop: 2 },

  list: { paddingHorizontal: 16, paddingBottom: 32 },

  card: {
    backgroundColor: C.card,
    borderRadius:    16,
    padding:         16,
    marginBottom:    12,
    borderWidth:     1,
    borderColor:     C.border,
  },
  cardTop:    { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  nodeIdRow:  { flexDirection: 'row', alignItems: 'center', gap: 8 },
  nodeId:     { fontSize: 16, fontWeight: '800', color: C.text },
  statusBadge:{
    flexDirection:  'row',
    alignItems:     'center',
    gap:            4,
    paddingVertical: 4,
    paddingHorizontal: 10,
    borderRadius:   12,
  },
  statusText: { fontSize: 12, fontWeight: '700' },

  locationRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 8 },
  locationText:{ fontSize: 13, color: C.subtext, flex: 1 },
  divider:     { height: 1, backgroundColor: C.border, marginVertical: 12 },

  readingsRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  ariBadge:    {
    backgroundColor: '#0A2B1E',
    borderRadius:    10,
    paddingVertical:  6,
    paddingHorizontal: 12,
    minWidth:         80,
  },
  ariLabel:    { fontSize: 14, fontWeight: '800' },
  ariRisk:     { fontSize: 11, fontWeight: '600', marginTop: 2 },
  noData:      { color: C.subtext, fontSize: 12 },

  lastReadingBlock: { flex: 1 },
  lastReadingLabel: { fontSize: 11, color: C.subtext },
  lastReadingTime:  { fontSize: 13, color: C.text, fontWeight: '600', marginTop: 2 },

  empty:     { alignItems: 'center', paddingTop: 80, gap: 12 },
  emptyText: { color: C.subtext, fontSize: 16 },
});
