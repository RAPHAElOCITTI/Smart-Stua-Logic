/**
 * GaugeChart Component — SVG-based circular gauge
 * Used for Temperature and Humidity display on Dashboard.
 */

import React, { useEffect, useRef } from 'react';
import { View, Text, StyleSheet, Animated } from 'react-native';
import Svg, { Circle, Path, G, Text as SvgText, Defs, LinearGradient, Stop } from 'react-native-svg';

const SIZE  = 140;
const CX    = SIZE / 2;
const CY    = SIZE / 2;
const RADIUS = 50;
const STROKE = 10;

// Arc from -225° to +45° (270° sweep)
const START_ANGLE = -225;
const END_ANGLE   = 45;
const SWEEP       = END_ANGLE - START_ANGLE; // 270°

function polarToCartesian(cx, cy, r, angleDeg) {
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  return {
    x: cx + r * Math.cos(rad),
    y: cy + r * Math.sin(rad),
  };
}

function describeArc(cx, cy, r, startAngle, endAngle) {
  const s = polarToCartesian(cx, cy, r, startAngle);
  const e = polarToCartesian(cx, cy, r, endAngle);
  const largeArc = endAngle - startAngle > 180 ? 1 : 0;
  return `M ${s.x} ${s.y} A ${r} ${r} 0 ${largeArc} 1 ${e.x} ${e.y}`;
}

export default function GaugeChart({ value, min, max, unit, label, color }) {
  const animValue = useRef(new Animated.Value(0)).current;

  const clampedPct = Math.max(0, Math.min(1, (value - min) / (max - min)));
  const fillAngle  = START_ANGLE + clampedPct * SWEEP;

  useEffect(() => {
    Animated.timing(animValue, {
      toValue:         clampedPct,
      duration:        800,
      useNativeDriver: false,
    }).start();
  }, [clampedPct]);

  const trackPath = describeArc(CX, CY, RADIUS, START_ANGLE, END_ANGLE);
  const fillPath  = clampedPct > 0
    ? describeArc(CX, CY, RADIUS, START_ANGLE, fillAngle)
    : null;

  // Needle tip calculation
  const needleEnd = polarToCartesian(CX, CY, RADIUS - 8, fillAngle);
  const needleBase1 = polarToCartesian(CX, CY, 6, fillAngle + 90);
  const needleBase2 = polarToCartesian(CX, CY, 6, fillAngle - 90);

  return (
    <View style={styles.container}>
      <Svg width={SIZE} height={SIZE}>
        <Defs>
          <LinearGradient id={`grad_${label}`} x1="0%" y1="0%" x2="100%" y2="0%">
            <Stop offset="0%" stopColor={color} stopOpacity="0.4" />
            <Stop offset="100%" stopColor={color} stopOpacity="1" />
          </LinearGradient>
        </Defs>

        {/* Track */}
        <Path
          d={trackPath}
          fill="none"
          stroke="#1E293B"
          strokeWidth={STROKE}
          strokeLinecap="round"
        />

        {/* Fill arc */}
        {fillPath && (
          <Path
            d={fillPath}
            fill="none"
            stroke={`url(#grad_${label})`}
            strokeWidth={STROKE}
            strokeLinecap="round"
          />
        )}

        {/* Needle */}
        <G>
          <Path
            d={`M ${needleBase1.x} ${needleBase1.y} L ${needleEnd.x} ${needleEnd.y} L ${needleBase2.x} ${needleBase2.y} Z`}
            fill={color}
            opacity={0.9}
          />
          <Circle cx={CX} cy={CY} r={6} fill="#1A2340" stroke={color} strokeWidth={2} />
        </G>

        {/* Value Text */}
        <SvgText
          x={CX}
          y={CY + 18}
          textAnchor="middle"
          fontSize="20"
          fontWeight="800"
          fill="#F0F4FF"
        >
          {typeof value === 'number' ? value.toFixed(1) : '--'}
        </SvgText>
        <SvgText
          x={CX}
          y={CY + 34}
          textAnchor="middle"
          fontSize="12"
          fill="#8892A4"
        >
          {unit}
        </SvgText>
      </Svg>

      {/* Label */}
      <Text style={[styles.label, { color }]}>{label}</Text>

      {/* Min / Max */}
      <View style={styles.minMaxRow}>
        <Text style={styles.minMax}>{min}{unit}</Text>
        <Text style={styles.minMax}>{max}{unit}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { alignItems: 'center', flex: 1 },
  label:     { fontSize: 13, fontWeight: '700', marginTop: -8 },
  minMaxRow: { flexDirection: 'row', justifyContent: 'space-between', width: SIZE, paddingHorizontal: 16 },
  minMax:    { fontSize: 10, color: '#4A5568' },
});
