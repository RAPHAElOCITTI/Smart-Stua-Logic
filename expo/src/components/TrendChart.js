/**
 * TrendChart Component
 * Historical line chart showing Temperature, Humidity, and Moisture trends
 * over the past 7 days using react-native-chart-kit.
 */

import React, { useMemo } from 'react';
import { View, Text, StyleSheet, Dimensions, ScrollView } from 'react-native';
import { LineChart } from 'react-native-chart-kit';
import { format } from 'date-fns';

const { width } = Dimensions.get('window');
const CHART_WIDTH = width - 48; // margin 16*2 + padding 8*2

export default function TrendChart({ readings }) {
  // Downsample to max 30 data points for performance
  const dataPoints = useMemo(() => {
    if (!readings || readings.length === 0) return [];
    const step = Math.max(1, Math.floor(readings.length / 30));
    return readings
      .slice()
      .reverse()  // oldest → newest
      .filter((_, idx) => idx % step === 0)
      .slice(-30);
  }, [readings]);

  if (dataPoints.length < 2) {
    return (
      <View style={styles.empty}>
        <Text style={styles.emptyText}>Insufficient data for trend chart</Text>
      </View>
    );
  }

  const labels = dataPoints.map((r, idx) => {
    if (idx === 0 || idx === Math.floor(dataPoints.length / 2) || idx === dataPoints.length - 1) {
      return format(new Date(r.recorded_at), 'MM/dd HH:mm');
    }
    return '';
  });

  const chartData = {
    labels,
    datasets: [
      {
        data:        dataPoints.map(r => r.temperature_c),
        color:       (opacity = 1) => `rgba(255, 149, 0, ${opacity})`,
        strokeWidth: 2,
      },
      {
        data:        dataPoints.map(r => r.humidity_pct),
        color:       (opacity = 1) => `rgba(10, 132, 255, ${opacity})`,
        strokeWidth: 2,
      },
      {
        data:        dataPoints.map(r => r.moisture_pct ?? 0),
        color:       (opacity = 1) => `rgba(0, 210, 106, ${opacity})`,
        strokeWidth: 2,
      },
    ],
    legend: ['Temperature (°C)', 'Humidity (%)', 'Moisture (%)'],
  };

  const chartConfig = {
    backgroundColor:         '#1A2340',
    backgroundGradientFrom:  '#1A2340',
    backgroundGradientTo:    '#141B2D',
    decimalPlaces:           1,
    color:                   (opacity = 1) => `rgba(240, 244, 255, ${opacity})`,
    labelColor:              (opacity = 1) => `rgba(136, 146, 164, ${opacity})`,
    style:                   { borderRadius: 12 },
    propsForDots:            { r: '3', strokeWidth: '1', stroke: '#2D3A55' },
    propsForBackgroundLines: { strokeDasharray: '', stroke: '#1E293B', strokeWidth: 1 },
  };

  return (
    <View>
      <ScrollView horizontal showsHorizontalScrollIndicator={false}>
        <LineChart
          data={chartData}
          width={Math.max(CHART_WIDTH, dataPoints.length * 28)}
          height={200}
          chartConfig={chartConfig}
          bezier
          style={styles.chart}
          withInnerLines={true}
          withOuterLines={false}
          withDots={dataPoints.length <= 20}
          withShadow={false}
          fromZero={false}
        />
      </ScrollView>

      {/* Legend */}
      <View style={styles.legend}>
        <View style={styles.legendItem}>
          <View style={[styles.legendDot, { backgroundColor: '#FF9500' }]} />
          <Text style={styles.legendText}>Temperature (°C)</Text>
        </View>
        <View style={styles.legendItem}>
          <View style={[styles.legendDot, { backgroundColor: '#0A84FF' }]} />
          <Text style={styles.legendText}>Humidity (%)</Text>
        </View>
        <View style={styles.legendItem}>
          <View style={[styles.legendDot, { backgroundColor: '#00D26A' }]} />
          <Text style={styles.legendText}>Moisture (%)</Text>
        </View>
      </View>

      {/* Stats summary */}
      <View style={styles.statsRow}>
        <StatBadge
          label="Avg Temp"
          value={avg(dataPoints.map(r => r.temperature_c)).toFixed(1) + '°C'}
          color="#FF9500"
        />
        <StatBadge
          label="Avg Humidity"
          value={avg(dataPoints.map(r => r.humidity_pct)).toFixed(1) + '%'}
          color="#0A84FF"
        />
        <StatBadge
          label="Avg Moisture"
          value={avg(dataPoints.map(r => r.moisture_pct ?? 0)).toFixed(1) + '%'}
          color="#00D26A"
        />
        <StatBadge
          label="Data Points"
          value={String(dataPoints.length)}
          color="#8892A4"
        />
      </View>
    </View>
  );
}

function StatBadge({ label, value, color }) {
  return (
    <View style={styles.statBadge}>
      <Text style={[styles.statValue, { color }]}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

function avg(arr) {
  if (!arr.length) return 0;
  return arr.reduce((a, b) => a + b, 0) / arr.length;
}

const styles = StyleSheet.create({
  chart:      { borderRadius: 12, marginLeft: -16 },
  empty:      { height: 120, alignItems: 'center', justifyContent: 'center' },
  emptyText:  { color: '#4A5568', fontSize: 14 },
  legend:     { flexDirection: 'row', gap: 16, marginTop: 8 },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  legendDot:  { width: 10, height: 10, borderRadius: 5 },
  legendText: { color: '#8892A4', fontSize: 12 },
  statsRow:   { flexDirection: 'row', marginTop: 12, gap: 8 },
  statBadge:  {
    flex:            1,
    backgroundColor: '#0A0F1E',
    borderRadius:    10,
    padding:         10,
    alignItems:      'center',
    borderWidth:     1,
    borderColor:     '#1E293B',
  },
  statValue: { fontSize: 15, fontWeight: '800' },
  statLabel: { fontSize: 11, color: '#4A5568', marginTop: 2 },
});
