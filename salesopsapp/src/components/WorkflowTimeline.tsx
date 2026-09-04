/**
 * WorkflowTimeline.tsx
 *
 * Vertical timeline showing live workflow steps with animated dots,
 * connecting lines, and status indicators.
 * Used in Chat and Outcome Report screens.
 */

import React, { useEffect, useRef } from 'react';
import { View, Text, StyleSheet, Animated } from 'react-native';
import { useTheme } from '../hooks/useTheme';
import { Check } from '../constants/icons';

export interface WorkflowStep {
  id: string;
  label: string;
  status: 'completed' | 'active' | 'pending';
}

interface WorkflowTimelineProps {
  steps: WorkflowStep[];
  title?: string;
}

const PulsingDot = ({ color }: { color: string }) => {
  const pulseAnim = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    const pulse = Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, {
          toValue: 1.6,
          duration: 800,
          useNativeDriver: true,
        }),
        Animated.timing(pulseAnim, {
          toValue: 1,
          duration: 800,
          useNativeDriver: true,
        }),
      ]),
    );
    pulse.start();
    return () => pulse.stop();
  }, [pulseAnim]);

  return (
    <View style={styles.dotContainer}>
      <Animated.View
        style={[
          styles.pulseRing,
          {
            backgroundColor: color + '30',
            transform: [{ scale: pulseAnim }],
          },
        ]}
      />
      <View style={[styles.activeDot, { backgroundColor: color }]} />
    </View>
  );
};

export const WorkflowTimeline = ({ steps, title }: WorkflowTimelineProps) => {
  const { colors, spacing, borderRadius, mode } = useTheme();

  const getStepColor = (status: WorkflowStep['status']) => {
    switch (status) {
      case 'completed': return colors.success;
      case 'active': return colors.accent;
      case 'pending': return colors.textMuted;
    }
  };

  return (
    <View
      style={[
        styles.container,
        {
          backgroundColor: mode === 'dark' ? colors.surface : colors.surfaceHighlight,
          borderColor: colors.border,
          borderRadius: borderRadius.lg,
          padding: spacing.md,
        },
      ]}>
      {title && (
        <Text style={[styles.title, { color: colors.text, marginBottom: spacing.md }]}>
          {title}
        </Text>
      )}

      {steps.map((step, index) => {
        const stepColor = getStepColor(step.status);
        const isLast = index === steps.length - 1;

        return (
          <View key={step.id} style={styles.stepRow}>
            {/* Timeline dot & line */}
            <View style={styles.timelineCol}>
              {step.status === 'active' ? (
                <PulsingDot color={stepColor} />
              ) : step.status === 'completed' ? (
                <View style={[styles.completedDot, { backgroundColor: stepColor + '20' }]}>
                  <Check size={10} color={stepColor} />
                </View>
              ) : (
                <View style={[styles.pendingDot, { borderColor: stepColor }]} />
              )}
              {!isLast && (
                <View
                  style={[
                    styles.line,
                    {
                      backgroundColor:
                        step.status === 'completed'
                          ? colors.success + '40'
                          : colors.border,
                    },
                  ]}
                />
              )}
            </View>

            {/* Step label */}
            <Text
              style={[
                styles.stepLabel,
                {
                  color:
                    step.status === 'pending'
                      ? colors.textMuted
                      : colors.text,
                  fontWeight: step.status === 'active' ? '600' : '400',
                },
              ]}>
              {step.label}
              {step.status === 'completed' && (
                <Text style={{ color: colors.success, fontSize: 12 }}>
                  {'  '}Completed
                </Text>
              )}
            </Text>
          </View>
        );
      })}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    borderWidth: 1,
  },
  title: {
    fontSize: 14,
    fontWeight: '600',
  },
  stepRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    minHeight: 36,
  },
  timelineCol: {
    width: 24,
    alignItems: 'center',
  },
  dotContainer: {
    width: 18,
    height: 18,
    justifyContent: 'center',
    alignItems: 'center',
  },
  pulseRing: {
    position: 'absolute',
    width: 18,
    height: 18,
    borderRadius: 9,
  },
  activeDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  completedDot: {
    width: 18,
    height: 18,
    borderRadius: 9,
    justifyContent: 'center',
    alignItems: 'center',
  },
  pendingDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    borderWidth: 2,
  },
  line: {
    width: 2,
    flex: 1,
    minHeight: 14,
    marginVertical: 2,
  },
  stepLabel: {
    fontSize: 13,
    lineHeight: 18,
    marginLeft: 10,
    flex: 1,
    paddingTop: 1,
  },
});
