/**
 * MoistureCard Component — Standalone card for moisture monitoring
 * Feature 1: Real-Time Moisture Monitoring Section
 */

import React from 'react';
import { View, Text, StyleSheet, Dimensions } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import Svg, { Circle, G, Text as SvgText } from 'react-native-svg';
import { getMoistureColor, getMoistureLabel } from '../api';

const { width } = Dimensions.get('window');

export default function MoistureCard({ moisturePct, nodeIdentifier, status }) {
  const hasReading = moisturePct !== null && moisturePct !== undefined;
  const color = getMoistureColor(moisturePct);
  const label = getMoistureLabel(moisturePct);

  // SVG configuration
  const size = 90;
  const strokeWidth = 8;
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const pct = hasReading ? Math.min(100, Math.max(0, moisturePct)) : 0;
  const strokeDashoffset = circumference - (pct / 100) * circumference;

  return (
    <View style={styles.card}>
      <View style={styles.header}>
        <View style={styles.titleRow}>
          <Ionicons name="water" size={20} color={color} />
          <Text style={styles.cardTitle}>Moisture Monitoring</Text>
        </View>
        <View style={[styles.badge, { borderColor: color }]}>
          <Text style={[styles.badgeText, { color }]}>{label}</Text>
        </View>
      </View>

      <View style={styles.contentRow}>
        {/* Circular indicator */}
        <View style={styles.indicatorContainer}>
          <Svg width={size} height={size}>
            <G rotation="-90" origin={`${size / 2}, ${size / 2}`}>
              <Circle
                cx={size / 2}
                cy={size / 2}
                r={radius}
                stroke="#1E293B"
                strokeWidth={strokeWidth}
                fill="transparent"
              />
              <Circle
                cx={size / 2}
                cy={size / 2}
                r={radius}
                stroke={color}
                strokeWidth={strokeWidth}
                strokeDasharray={circumference}
                strokeDashoffset={strokeDashoffset}
                strokeLinecap="round"
                fill="transparent"
              />
            </G>
            <SvgText
              x={size / 2}
              y={size / 2 + 6}
              textAnchor="middle"
              fontSize="18"
              fontWeight="800"
              fill="#F0F4FF"
            >
              {hasReading ? `${pct.toFixed(0)}%` : '--'}
            </SvgText>
          </Svg>
        </View>

        {/* Moisture Info Details */}
        <View style={styles.infoCol}>
          <View style={styles.infoItem}>
            <Text style={styles.infoLabel}>Sensor Node</Text>
            <Text style={styles.infoValue}>{nodeIdentifier || 'N/A'}</Text>
          </View>
          <View style={styles.infoItem}>
            <Text style={styles.infoLabel}>Status</Text>
            <View style={styles.statusRow}>
              <View style={[styles.statusDot, { backgroundColor: status === 'active' ? '#00D26A' : '#FF3B30' }]} />
              <Text style={styles.statusText}>{status === 'active' ? 'Online' : 'Offline'}</Text>
            </View>
          </View>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#1A2340',
    borderRadius: 16,
    padding: 16,
    marginHorizontal: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#1E293B',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  titleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  cardTitle: {
    color: '#F0F4FF',
    fontSize: 15,
    fontWeight: '700',
  },
  badge: {
    borderWidth: 1,
    borderRadius: 12,
    paddingVertical: 3,
    paddingHorizontal: 10,
  },
  badgeText: {
    fontSize: 11,
    fontWeight: '700',
    textTransform: 'uppercase',
  },
  contentRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 24,
  },
  indicatorContainer: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  infoCol: {
    flex: 1,
    gap: 12,
  },
  infoItem: {
    gap: 2,
  },
  infoLabel: {
    color: '#8892A4',
    fontSize: 11,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  infoValue: {
    color: '#F0F4FF',
    fontSize: 14,
    fontWeight: '700',
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  statusText: {
    color: '#F0F4FF',
    fontSize: 14,
    fontWeight: '600',
  },
});
