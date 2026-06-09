/**
 * Dashboard Screen — Main Smart-Stua Screen
 * UC: "View Dashboard / ARI"
 *
 * Features:
 *   - Node selector dropdown
 *   - Real-time temperature & humidity gauges
 *   - ARI Risk Indicator with pulsing animation for High risk
 *   - Dryer status + manual override button
 *   - 7-day temperature/humidity/ARI trend chart
 *   - 30-second auto-refresh polling
 *   - Pull-to-refresh
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  View, Text, ScrollView, TouchableOpacity, RefreshControl,
  StyleSheet, Animated, Dimensions, ActivityIndicator,
  SafeAreaView, Platform, useWindowDimensions,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import {
  fetchDashboardSummary, fetchDeviceReadings,
  sendDryerCommand, startPolling, stopPolling,
} from '../api';
import GaugeChart  from '../components/GaugeChart';
import RiskIndicator from '../components/RiskIndicator';
import TrendChart  from '../components/TrendChart';

const { width } = Dimensions.get('window');

// ─── Design Tokens ────────────────────────────────────────────────────────────
const C = {
  bg:       '#0A0F1E',
  surface:  '#141B2D',
  card:     '#1A2340',
  border:   '#1E293B',
  text:     '#F0F4FF',
  subtext:  '#8892A4',
  primary:  '#00D26A',
  danger:   '#FF3B30',
  warning:  '#FF9500',
  blue:     '#0A84FF',
};

export default function DashboardScreen() {
  const { width: windowWidth } = useWindowDimensions();
  const responsiveTitleSize = Math.min(Math.max(windowWidth * 0.065, 22), 34);
  const [nodes, setNodes]               = useState([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [readings, setReadings]         = useState([]);
  const [loading, setLoading]           = useState(true);
  const [refreshing, setRefreshing]     = useState(false);
  const [error, setError]               = useState(null);
  const [lastUpdated, setLastUpdated]   = useState(null);
  const [dryerLoading, setDryerLoading] = useState(false);

  const selectedNode = nodes[selectedIndex] || null;

  // ─── Data Fetching ─────────────────────────────────────────────────────────
  const fetchData = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    setError(null);
    try {
      const summary = await fetchDashboardSummary();
      setNodes(summary.nodes || []);
      setLastUpdated(new Date());

      // Fetch 7-day readings for selected node
      if (summary.nodes && summary.nodes.length > 0) {
        const node = summary.nodes[selectedIndex] || summary.nodes[0];
        const hist = await fetchDeviceReadings(node.node_id, { days: 7, limit: 200 });
        setReadings(hist.readings || []);
      }
    } catch (err) {
      setError('Unable to connect to server. Check your network settings.');
      console.error('[Dashboard] Fetch error:', err.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [selectedIndex]);

  // 30-second polling
  useEffect(() => {
    fetchData();
    startPolling(() => fetchData(true), 30000);
    return () => stopPolling();
  }, [selectedIndex]);

  const onRefresh = () => {
    setRefreshing(true);
    fetchData();
  };

  // ─── Dryer Override ────────────────────────────────────────────────────────
  const handleDryerToggle = async () => {
    if (!selectedNode) return;
    setDryerLoading(true);
    try {
      const action = selectedNode.dryer_active ? 'OFF' : 'ON';
      await sendDryerCommand(selectedNode.node_id, action);
      await fetchData(true);
    } catch (err) {
      console.error('[Dashboard] Dryer command failed:', err.message);
    } finally {
      setDryerLoading(false);
    }
  };

  // ─── Render: Loading ───────────────────────────────────────────────────────
  if (loading) {
    return (
      <SafeAreaView style={[styles.container, styles.centered]}>
        <ActivityIndicator size="large" color={C.primary} />
        <Text style={styles.loadingText}>Loading Smart-Stua data...</Text>
      </SafeAreaView>
    );
  }

  // ─── Render: Error ─────────────────────────────────────────────────────────
  if (error && nodes.length === 0) {
    return (
      <SafeAreaView style={[styles.container, styles.centered]}>
        <Ionicons name="cloud-offline-outline" size={64} color={C.danger} />
        <Text style={styles.errorText}>{error}</Text>
        <TouchableOpacity style={styles.retryBtn} onPress={() => fetchData()}>
          <Text style={styles.retryBtnText}>Retry</Text>
        </TouchableOpacity>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView
        style={styles.scroll}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor={C.primary}
          />
        }
        showsVerticalScrollIndicator={false}
      >
        {/* Header */}
        <LinearGradient
          colors={['#0A2B1E', '#0A0F1E']}
          style={styles.header}
        >
          <View style={styles.headerRow}>
            <View>
              <Text style={[styles.headerTitle, { fontSize: responsiveTitleSize }]}>Smart-Stua</Text>
              <Text style={styles.headerSubtitle}>Aflatoxin Prevention System</Text>
            </View>
            <View style={styles.headerRight}>
              <Ionicons name="leaf" size={28} color={C.primary} />
              {lastUpdated && (
                <Text style={styles.updateTime}>
                  {lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </Text>
              )}
            </View>
          </View>
        </LinearGradient>

        {/* Node Selector */}
        {nodes.length > 1 && (
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            style={styles.nodeSelectorRow}
          >
            {nodes.map((node, idx) => (
              <TouchableOpacity
                key={node.node_id}
                style={[
                  styles.nodeChip,
                  idx === selectedIndex && styles.nodeChipActive,
                ]}
                onPress={() => setSelectedIndex(idx)}
              >
                <View
                  style={[
                    styles.nodeStatusDot,
                    { backgroundColor: node.status === 'active' ? C.primary : C.danger },
                  ]}
                />
                <Text
                  style={[
                    styles.nodeChipText,
                    idx === selectedIndex && styles.nodeChipTextActive,
                  ]}
                >
                  {node.node_identifier}
                </Text>
              </TouchableOpacity>
            ))}
          </ScrollView>
        )}

        {selectedNode && (
          <>
            {/* Location Label */}
            <View style={styles.locationRow}>
              <Ionicons name="location-outline" size={16} color={C.subtext} />
              <Text style={styles.locationText}>{selectedNode.location_label}</Text>
            </View>

            {/* ARI Risk Indicator */}
            <RiskIndicator
              riskLevel={selectedNode.risk_level || 'Low'}
              ariScore={selectedNode.ari_value || 0}
            />

            {/* Gauge Row */}
            <View style={styles.gaugeRow}>
              <GaugeChart
                value={selectedNode.temperature_c ?? 0}
                min={0}
                max={50}
                unit="°C"
                label="Temperature"
                color="#FF9500"
              />
              <GaugeChart
                value={selectedNode.humidity_pct ?? 0}
                min={0}
                max={100}
                unit="%"
                label="Humidity"
                color="#0A84FF"
              />
            </View>

            {/* Dryer Status Card */}
            <View style={styles.card}>
              <View style={styles.dryerRow}>
                <View style={styles.dryerInfo}>
                  <Ionicons
                    name={selectedNode.dryer_active ? 'flame' : 'flame-outline'}
                    size={32}
                    color={selectedNode.dryer_active ? C.danger : C.subtext}
                  />
                  <View style={styles.dryerTextBlock}>
                    <Text style={styles.cardLabel}>Grain Dryer</Text>
                    <Text
                      style={[
                        styles.dryerStatus,
                        { color: selectedNode.dryer_active ? C.danger : C.primary },
                      ]}
                    >
                      {selectedNode.dryer_active ? '● ACTIVE' : '○ INACTIVE'}
                    </Text>
                  </View>
                </View>
                <TouchableOpacity
                  style={[
                    styles.dryerBtn,
                    { backgroundColor: selectedNode.dryer_active ? '#3A1A1A' : '#0A2B1E' },
                  ]}
                  onPress={handleDryerToggle}
                  disabled={dryerLoading}
                >
                  {dryerLoading ? (
                    <ActivityIndicator size="small" color={C.primary} />
                  ) : (
                    <Text
                      style={[
                        styles.dryerBtnText,
                        { color: selectedNode.dryer_active ? C.danger : C.primary },
                      ]}
                    >
                      {selectedNode.dryer_active ? 'Turn OFF' : 'Turn ON'}
                    </Text>
                  )}
                </TouchableOpacity>
              </View>
            </View>

            {/* 7-Day Trend Chart */}
            {readings.length > 0 && (
              <View style={styles.card}>
                <Text style={styles.cardTitle}>7-Day Environmental Trend</Text>
                <TrendChart readings={readings} />
              </View>
            )}

            {/* Stats Row */}
            <View style={styles.statsRow}>
              <View style={styles.statCard}>
                <Text style={styles.statValue}>
                  {selectedNode.ari_value != null
                    ? selectedNode.ari_value.toFixed(1)
                    : '--'}
                </Text>
                <Text style={styles.statLabel}>ARI Score</Text>
              </View>
              <View style={styles.statCard}>
                <Text style={[styles.statValue, { color: C.primary }]}>
                  {nodes.filter(n => n.status === 'active').length}
                </Text>
                <Text style={styles.statLabel}>Active Nodes</Text>
              </View>
              <View style={styles.statCard}>
                <Text style={[styles.statValue, { color: C.warning }]}>
                  {nodes.filter(n => n.risk_level === 'High' || n.risk_level === 'Medium').length}
                </Text>
                <Text style={styles.statLabel}>At Risk</Text>
              </View>
            </View>
          </>
        )}

        {nodes.length === 0 && !loading && (
          <View style={styles.emptyState}>
            <Ionicons name="hardware-chip-outline" size={64} color={C.subtext} />
            <Text style={styles.emptyText}>No sensor nodes registered</Text>
            <Text style={styles.emptySubtext}>
              Add sensor nodes via the admin panel
            </Text>
          </View>
        )}

        <View style={{ height: 32 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container:   { flex: 1, backgroundColor: C.bg },
  scroll:      { flex: 1 },
  centered:    { alignItems: 'center', justifyContent: 'center', gap: 16 },
  header:      {
    paddingTop:    Platform.OS === 'ios' ? 12 : 16,
    paddingBottom: 20,
    paddingHorizontal: 20,
  },
  headerRow:      { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  headerTitle:    { fontSize: 26, fontWeight: '800', color: C.text, letterSpacing: -0.5 },
  headerSubtitle: { fontSize: 13, color: C.subtext, marginTop: 2 },
  headerRight:    { alignItems: 'center', gap: 4 },
  updateTime:     { fontSize: 11, color: C.subtext },

  nodeSelectorRow: { paddingHorizontal: 16, paddingVertical: 12 },
  nodeChip:        {
    flexDirection:  'row',
    alignItems:     'center',
    backgroundColor: C.card,
    borderRadius:   20,
    paddingVertical: 8,
    paddingHorizontal: 14,
    marginRight:    8,
    borderWidth:    1,
    borderColor:    C.border,
    gap:            6,
  },
  nodeChipActive:     { borderColor: C.primary, backgroundColor: '#0A2B1E' },
  nodeStatusDot:      { width: 8, height: 8, borderRadius: 4 },
  nodeChipText:       { color: C.subtext, fontSize: 13, fontWeight: '600' },
  nodeChipTextActive: { color: C.primary },

  locationRow: {
    flexDirection:  'row',
    alignItems:     'center',
    paddingHorizontal: 20,
    marginBottom:   8,
    gap:            6,
  },
  locationText: { color: C.subtext, fontSize: 13 },

  gaugeRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    paddingHorizontal: 16,
    marginVertical: 8,
  },

  card: {
    backgroundColor: C.card,
    borderRadius:    16,
    padding:         16,
    marginHorizontal: 16,
    marginBottom:    12,
    borderWidth:     1,
    borderColor:     C.border,
  },
  cardTitle: { color: C.text, fontSize: 15, fontWeight: '700', marginBottom: 12 },
  cardLabel: { color: C.subtext, fontSize: 12 },

  dryerRow:      { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  dryerInfo:     { flexDirection: 'row', alignItems: 'center', gap: 12 },
  dryerTextBlock:{ gap: 4 },
  dryerStatus:   { fontSize: 14, fontWeight: '700', letterSpacing: 1 },
  dryerBtn:      {
    paddingVertical:   10,
    paddingHorizontal: 20,
    borderRadius:      10,
    borderWidth:       1,
    borderColor:       C.border,
    minWidth:          90,
    alignItems:        'center',
  },
  dryerBtnText:  { fontSize: 14, fontWeight: '700' },

  statsRow:  {
    flexDirection:  'row',
    paddingHorizontal: 16,
    marginBottom:   12,
    gap:            10,
  },
  statCard:  {
    flex:            1,
    backgroundColor: C.card,
    borderRadius:    14,
    padding:         14,
    alignItems:      'center',
    borderWidth:     1,
    borderColor:     C.border,
  },
  statValue: { fontSize: 24, fontWeight: '800', color: C.text },
  statLabel: { fontSize: 11, color: C.subtext, marginTop: 4, textAlign: 'center' },

  loadingText: { color: C.subtext, fontSize: 15, textAlign: 'center' },
  errorText:   { color: C.subtext, fontSize: 15, textAlign: 'center', paddingHorizontal: 32 },
  retryBtn:    {
    backgroundColor: C.primary,
    paddingVertical: 12,
    paddingHorizontal: 32,
    borderRadius:    10,
  },
  retryBtnText: { color: '#000', fontWeight: '700', fontSize: 15 },

  emptyState:   { alignItems: 'center', paddingTop: 80, gap: 12 },
  emptyText:    { color: C.text, fontSize: 18, fontWeight: '700' },
  emptySubtext: { color: C.subtext, fontSize: 14 },
});
