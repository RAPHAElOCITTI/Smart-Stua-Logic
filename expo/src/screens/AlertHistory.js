/**
 * AlertHistory Screen
 * UC: "Receive SMS/Email Alert" + "View Historical Reports"
 *
 * Features:
 *   - Paginated alert list with risk-level color badges
 *   - Filter by risk level (Low / Medium / High) and last N days
 *   - Acknowledge alerts (mark action_taken = true)
 *   - Pull-to-refresh
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, FlatList, TouchableOpacity, StyleSheet,
  SafeAreaView, ActivityIndicator, RefreshControl, Modal, useWindowDimensions,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { fetchAlerts, acknowledgeAlert } from '../api';
import { format, formatDistanceToNow } from 'date-fns';

const C = {
  bg:      '#0A0F1E',
  card:    '#1A2340',
  border:  '#1E293B',
  text:    '#F0F4FF',
  subtext: '#8892A4',
  primary: '#00D26A',
  danger:  '#FF3B30',
  warning: '#FF9500',
};

const RISK_CONFIG = {
  High:   { color: C.danger,  bg: '#3A1A1A', icon: 'alert-circle' },
  Medium: { color: C.warning, bg: '#2A1E0A', icon: 'warning' },
  Low:    { color: C.primary, bg: '#0A2B1E', icon: 'checkmark-circle' },
};

const DAY_FILTERS  = [
  { label: '24h', days: 1 },
  { label: '7d',  days: 7 },
  { label: '30d', days: 30 },
  { label: 'All', days: 365 },
];
const RISK_FILTERS = ['All', 'High', 'Medium', 'Low'];

const ALERT_TYPE_CONFIG = {
  ari_risk:         { icon: 'shield-outline',         label: 'ARI Risk' },
  threshold_breach: { icon: 'thermometer-outline',    label: 'Breach' },
  node_offline:     { icon: 'cloud-offline-outline',  label: 'Offline' },
};

export default function AlertHistory() {
  const { width } = useWindowDimensions();
  const responsiveTitleSize = Math.min(Math.max(width * 0.065, 22), 34);
  const [alerts, setAlerts]         = useState([]);
  const [loading, setLoading]       = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [riskFilter, setRiskFilter] = useState('All');
  const [dayFilter, setDayFilter]   = useState(7);
  const [selected, setSelected]     = useState(null);

  const loadAlerts = useCallback(async () => {
    try {
      const params = { days: dayFilter };
      if (riskFilter !== 'All') params.risk_level = riskFilter;
      const data = await fetchAlerts(params);
      setAlerts(data.alerts || []);
    } catch (err) {
      console.error('[Alerts] Fetch failed:', err.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [riskFilter, dayFilter]);

  useEffect(() => { loadAlerts(); }, [riskFilter, dayFilter]);

  const onRefresh = () => { setRefreshing(true); loadAlerts(); };

  const handleAcknowledge = async alertId => {
    try {
      await acknowledgeAlert(alertId);
      setAlerts(prev => prev.map(a =>
        a.alert_id === alertId ? { ...a, action_taken: true } : a
      ));
      setSelected(null);
    } catch (err) {
      console.error('[Alerts] Acknowledge failed:', err.message);
    }
  };

  const renderAlert = ({ item }) => {
    const risk = RISK_CONFIG[item.risk_level] || RISK_CONFIG.Low;
    const typeCfg = ALERT_TYPE_CONFIG[item.alert_type] || ALERT_TYPE_CONFIG.ari_risk;
    return (
      <TouchableOpacity
        style={[styles.card, item.action_taken && styles.cardAcknowledged]}
        activeOpacity={0.8}
        onPress={() => setSelected(item)}
      >
        <View style={styles.cardTop}>
          <View style={{ flexDirection: 'row', gap: 6, alignItems: 'center' }}>
            <View style={[styles.riskBadge, { backgroundColor: risk.bg }]}>
              <Ionicons name={risk.icon} size={12} color={risk.color} />
              <Text style={[styles.riskText, { color: risk.color }]}>
                {item.risk_level.toUpperCase()}
              </Text>
            </View>
            <View style={styles.typeBadge}>
              <Ionicons name={typeCfg.icon} size={12} color="#8892A4" />
              <Text style={styles.typeText}>{typeCfg.label}</Text>
            </View>
          </View>
          <Text style={styles.timestamp}>
            {formatDistanceToNow(new Date(item.sent_at), { addSuffix: true })}
          </Text>
        </View>

        <View style={styles.infoRow}>
          <Ionicons name="location-outline" size={13} color={C.subtext} />
          <Text style={styles.location}>{item.node_location || item.node_identifier}</Text>
          {item.ari_value !== null && item.ari_value !== undefined && (
            <Text style={[styles.ariValue, { color: risk.color }]}>
              ARI {item.ari_value.toFixed(1)}
            </Text>
          )}
        </View>

        <Text style={styles.messagePreview} numberOfLines={2}>{item.message}</Text>

        <View style={styles.cardFooter}>
          <View style={styles.sentToRow}>
            <Ionicons name="phone-portrait-outline" size={12} color={C.subtext} />
            <Text style={styles.sentTo}>{item.sent_to}</Text>
          </View>
          {item.action_taken ? (
            <View style={styles.ackedBadge}>
              <Ionicons name="checkmark-done" size={12} color={C.primary} />
              <Text style={styles.ackedText}>Acknowledged</Text>
            </View>
          ) : (
            <TouchableOpacity
              style={styles.ackBtn}
              onPress={() => handleAcknowledge(item.alert_id)}
            >
              <Text style={styles.ackBtnText}>Acknowledge</Text>
            </TouchableOpacity>
          )}
        </View>
      </TouchableOpacity>
    );
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={[styles.title, { fontSize: responsiveTitleSize }]}>Alert History</Text>
        <Text style={styles.subtitle}>{alerts.length} alert{alerts.length !== 1 ? 's' : ''}</Text>
      </View>

      <View style={styles.filterRow}>
        {RISK_FILTERS.map(f => (
          <TouchableOpacity
            key={f}
            style={[styles.chip, riskFilter === f && styles.chipActive]}
            onPress={() => setRiskFilter(f)}
          >
            <Text style={[styles.chipText, riskFilter === f && styles.chipTextActive]}>{f}</Text>
          </TouchableOpacity>
        ))}
      </View>

      <View style={styles.filterRow}>
        {DAY_FILTERS.map(({ label, days }) => (
          <TouchableOpacity
            key={label}
            style={[styles.chip, dayFilter === days && styles.chipActive]}
            onPress={() => setDayFilter(days)}
          >
            <Text style={[styles.chipText, dayFilter === days && styles.chipTextActive]}>{label}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {loading ? (
        <View style={styles.centered}>
          <ActivityIndicator size="large" color={C.primary} />
        </View>
      ) : (
        <FlatList
          data={alerts}
          keyExtractor={item => String(item.alert_id)}
          renderItem={renderAlert}
          contentContainerStyle={styles.list}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.primary} />
          }
          ListEmptyComponent={
            <View style={styles.empty}>
              <Ionicons name="notifications-off-outline" size={60} color={C.subtext} />
              <Text style={styles.emptyText}>No alerts found</Text>
              <Text style={styles.emptySubtext}>Adjust filters or check back later</Text>
            </View>
          }
        />
      )}

      <Modal
        visible={!!selected}
        transparent
        animationType="slide"
        onRequestClose={() => setSelected(null)}
      >
        {selected && (() => {
          const risk = RISK_CONFIG[selected.risk_level] || RISK_CONFIG.Low;
          return (
            <View style={styles.modalBackdrop}>
              <View style={styles.modalCard}>
                <View style={styles.modalHeader}>
                  <View style={[styles.riskBadge, { backgroundColor: risk.bg }]}>
                    <Ionicons name={risk.icon} size={16} color={risk.color} />
                    <Text style={[styles.riskText, { color: risk.color }]}>
                      {selected.risk_level.toUpperCase()} RISK
                    </Text>
                  </View>
                  <TouchableOpacity onPress={() => setSelected(null)}>
                    <Ionicons name="close" size={24} color={C.subtext} />
                  </TouchableOpacity>
                </View>

                <Text style={styles.modalLabel}>Node</Text>
                <Text style={styles.modalValue}>{selected.node_identifier}</Text>
                <Text style={styles.modalLabel}>Location</Text>
                <Text style={styles.modalValue}>{selected.node_location}</Text>
                <Text style={styles.modalLabel}>ARI Score</Text>
                <Text style={styles.modalValue}>
                  {selected.ari_value !== null && selected.ari_value !== undefined ? `${selected.ari_value.toFixed(2)} / 100` : 'N/A'}
                </Text>
                <Text style={styles.modalLabel}>Time</Text>
                <Text style={styles.modalValue}>{format(new Date(selected.sent_at), 'PPpp')}</Text>
                <Text style={styles.modalLabel}>Message</Text>
                <Text style={[styles.modalValue, { fontSize: 12 }]}>{selected.message}</Text>
                <Text style={styles.modalLabel}>Sent To</Text>
                <Text style={styles.modalValue}>{selected.sent_to}</Text>

                {!selected.action_taken && (
                  <TouchableOpacity
                    style={styles.modalAckBtn}
                    onPress={() => handleAcknowledge(selected.alert_id)}
                  >
                    <Ionicons name="checkmark-done" size={18} color="#000" />
                    <Text style={styles.modalAckBtnText}>Mark as Acknowledged</Text>
                  </TouchableOpacity>
                )}
              </View>
            </View>
          );
        })()}
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container:  { flex: 1, backgroundColor: C.bg },
  centered:   { flex: 1, alignItems: 'center', justifyContent: 'center' },
  header:     { padding: 20, paddingTop: 16 },
  title:      { fontSize: 26, fontWeight: '800', color: C.text },
  subtitle:   { fontSize: 13, color: C.subtext, marginTop: 2 },
  filterRow:  { flexDirection: 'row', paddingHorizontal: 16, marginBottom: 8, gap: 8 },
  chip:       { paddingVertical: 6, paddingHorizontal: 14, borderRadius: 20, backgroundColor: C.card, borderWidth: 1, borderColor: C.border },
  chipActive:     { borderColor: C.primary, backgroundColor: '#0A2B1E' },
  chipText:       { color: C.subtext, fontSize: 13, fontWeight: '600' },
  chipTextActive: { color: C.primary },
  list:           { paddingHorizontal: 16, paddingBottom: 32 },
  card:           { backgroundColor: C.card, borderRadius: 14, padding: 14, marginBottom: 10, borderWidth: 1, borderColor: C.border },
  cardAcknowledged: { opacity: 0.55 },
  cardTop:    { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  riskBadge:  { flexDirection: 'row', alignItems: 'center', gap: 5, paddingVertical: 4, paddingHorizontal: 10, borderRadius: 10 },
  riskText:   { fontSize: 12, fontWeight: '800', letterSpacing: 0.5 },
  timestamp:  { color: C.subtext, fontSize: 12 },
  infoRow:    { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 6 },
  location:   { flex: 1, color: C.subtext, fontSize: 13 },
  ariValue:   { fontSize: 13, fontWeight: '800' },
  messagePreview: { color: C.text, fontSize: 12, lineHeight: 18, marginBottom: 10 },
  cardFooter: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  sentToRow:  { flexDirection: 'row', alignItems: 'center', gap: 4 },
  sentTo:     { color: C.subtext, fontSize: 12 },
  ackedBadge: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  ackedText:  { color: C.primary, fontSize: 12, fontWeight: '600' },
  ackBtn:     { backgroundColor: '#0A2B1E', paddingVertical: 5, paddingHorizontal: 12, borderRadius: 8, borderWidth: 1, borderColor: C.primary },
  ackBtnText: { color: C.primary, fontSize: 12, fontWeight: '700' },
  empty:      { alignItems: 'center', paddingTop: 60, gap: 10 },
  emptyText:  { color: C.text, fontSize: 18, fontWeight: '700' },
  emptySubtext: { color: C.subtext, fontSize: 14 },
  modalBackdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.75)', justifyContent: 'flex-end' },
  modalCard:  { backgroundColor: '#141B2D', borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 24, paddingBottom: 40, gap: 8 },
  modalHeader:{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  modalLabel: { color: C.subtext, fontSize: 12, marginTop: 8 },
  modalValue: { color: C.text, fontSize: 15, fontWeight: '600' },
  modalAckBtn:{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: C.primary, borderRadius: 12, paddingVertical: 14, marginTop: 16 },
  modalAckBtnText: { color: '#000', fontSize: 16, fontWeight: '800' },
  typeBadge:  { flexDirection: 'row', alignItems: 'center', gap: 4, paddingVertical: 4, paddingHorizontal: 8, borderRadius: 8, backgroundColor: '#1E293B' },
  typeText:   { color: '#8892A4', fontSize: 11, fontWeight: '700' },
});
