/**
 * RiskIndicator Component
 * Large color-coded ARI risk badge with:
 *   Low    → Green + checkmark icon (static)
 *   Medium → Amber + warning icon (slight pulse)
 *   High   → Red + danger icon + pulsing animation
 */

import React, { useEffect, useRef } from 'react';
import { View, Text, StyleSheet, Animated } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

const RISK_CONFIG = {
  High: {
    icon:       'alert-circle',
    color:      '#FF3B30',
    bgColor:    '#3A1A1A',
    borderColor:'#7A2020',
    label:      'HIGH RISK',
    pulse:      true,
  },
  Medium: {
    icon:       'warning',
    color:      '#FF9500',
    bgColor:    '#2A1E0A',
    borderColor:'#5A3A00',
    label:      'MEDIUM RISK',
    pulse:      false,
  },
  Low: {
    icon:       'checkmark-circle',
    color:      '#34C759',
    bgColor:    '#0A2B1E',
    borderColor:'#0A4A2A',
    label:      'LOW RISK',
    pulse:      false,
  },
};

export default function RiskIndicator({ riskLevel = 'Low', ariScore = 0 }) {
  const config = RISK_CONFIG[riskLevel] || RISK_CONFIG.Low;
  const pulseAnim = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    if (config.pulse) {
      Animated.loop(
        Animated.sequence([
          Animated.timing(pulseAnim, {
            toValue: 1.08,
            duration: 700,
            useNativeDriver: true,
          }),
          Animated.timing(pulseAnim, {
            toValue: 1,
            duration: 700,
            useNativeDriver: true,
          }),
        ])
      ).start();
    } else {
      pulseAnim.setValue(1);
    }
    return () => pulseAnim.stopAnimation();
  }, [riskLevel]);

  return (
    <Animated.View
      style={[
        styles.container,
        {
          backgroundColor: config.bgColor,
          borderColor:     config.borderColor,
          transform:       [{ scale: pulseAnim }],
        },
      ]}
    >
      <Ionicons name={config.icon} size={40} color={config.color} />

      <View style={styles.textBlock}>
        <Text style={[styles.riskLabel, { color: config.color }]}>
          {config.label}
        </Text>
        <Text style={styles.ariScore}>
          ARI:{' '}
          <Text style={[styles.ariValue, { color: config.color }]}>
            {typeof ariScore === 'number' ? ariScore.toFixed(1) : '--'}
          </Text>
          <Text style={styles.ariMax}> / 100</Text>
        </Text>
      </View>

      {/* ARI progress bar */}
      <View style={styles.progressTrack}>
        <View
          style={[
            styles.progressFill,
            {
              width:           `${Math.min(100, ariScore)}%`,
              backgroundColor: config.color,
            },
          ]}
        />
      </View>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginHorizontal: 16,
    marginVertical:   8,
    borderRadius:     18,
    borderWidth:      1.5,
    padding:          18,
    flexDirection:    'row',
    alignItems:       'center',
    gap:              14,
  },
  textBlock: { flex: 1 },
  riskLabel: {
    fontSize:    18,
    fontWeight:  '900',
    letterSpacing: 1.5,
    marginBottom: 4,
  },
  ariScore:   { color: '#8892A4', fontSize: 14 },
  ariValue:   { fontWeight: '800', fontSize: 16 },
  ariMax:     { color: '#4A5568', fontSize: 12 },
  progressTrack: {
    position:       'absolute',
    bottom:         0,
    left:           16,
    right:          16,
    height:         4,
    backgroundColor:'#1E293B',
    borderRadius:   2,
    overflow:       'hidden',
  },
  progressFill: {
    height:       4,
    borderRadius: 2,
    opacity:      0.8,
  },
});
