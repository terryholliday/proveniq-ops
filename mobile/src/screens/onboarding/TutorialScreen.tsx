/**
 * PROVENIQ Ops - Tutorial Screen
 * Quick walkthrough of how to use the scanner
 */

import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  SafeAreaView,
  Dimensions,
  TouchableOpacity,
} from 'react-native';
import { colors, typography, spacing } from '../../theme';
import { HudButton } from '../../components';

interface TutorialScreenProps {
  onContinue: () => void;
  onSkip: () => void;
  onBack: () => void;
}

interface TutorialStep {
  icon: string;
  title: string;
  description: string;
}

const TUTORIAL_STEPS: TutorialStep[] = [
  {
    icon: '📷',
    title: 'Point & Scan',
    description: 'Open the scanner and point your camera at items on the shelf. The app will automatically detect barcodes.',
  },
  {
    icon: '✅',
    title: 'Review Items',
    description: 'See detected items in real-time. Check quantities against what you expect. Flag any discrepancies.',
  },
  {
    icon: '🔄',
    title: 'Auto-Reorder',
    description: 'When items fall below par level, the system can automatically create orders with your vendors.',
  },
  {
    icon: '📊',
    title: 'Track Everything',
    description: 'View shrinkage reports, order history, and inventory levels across all your locations.',
  },
];

const { width } = Dimensions.get('window');

export function TutorialScreen({ onContinue, onSkip, onBack }: TutorialScreenProps) {
  const [currentStep, setCurrentStep] = useState(0);

  const isLastStep = currentStep === TUTORIAL_STEPS.length - 1;
  const step = TUTORIAL_STEPS[currentStep];

  const handleNext = () => {
    if (isLastStep) {
      onContinue();
    } else {
      setCurrentStep(currentStep + 1);
    }
  };

  const handlePrev = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    } else {
      onBack();
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      {/* Progress */}
      <View style={styles.progress}>
        <View style={styles.progressDot} />
        <View style={styles.progressDot} />
        <View style={styles.progressDot} />
        <View style={styles.progressDot} />
        <View style={styles.progressDot} />
        <View style={styles.progressDot} />
        <View style={[styles.progressDot, styles.progressDotActive]} />
      </View>

      {/* Skip Button */}
      <TouchableOpacity style={styles.skipButton} onPress={onSkip}>
        <Text style={styles.skipText}>Skip Tutorial</Text>
      </TouchableOpacity>

      {/* Tutorial Content */}
      <View style={styles.content}>
        <View style={styles.stepIndicator}>
          {TUTORIAL_STEPS.map((_, index) => (
            <View
              key={index}
              style={[
                styles.stepDot,
                index === currentStep && styles.stepDotActive,
                index < currentStep && styles.stepDotComplete,
              ]}
            />
          ))}
        </View>

        <View style={styles.iconContainer}>
          <Text style={styles.icon}>{step.icon}</Text>
        </View>

        <Text style={styles.title}>{step.title}</Text>
        <Text style={styles.description}>{step.description}</Text>

        <Text style={styles.stepCount}>
          {currentStep + 1} of {TUTORIAL_STEPS.length}
        </Text>
      </View>

      {/* Footer */}
      <View style={styles.footer}>
        <HudButton
          title={currentStep === 0 ? 'BACK' : 'PREVIOUS'}
          onPress={handlePrev}
          variant="ghost"
          style={styles.backButton}
        />
        <HudButton
          title={isLastStep ? 'FINISH' : 'NEXT'}
          onPress={handleNext}
          style={styles.continueButton}
        />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bgPrimary,
  },
  progress: {
    flexDirection: 'row',
    justifyContent: 'center',
    paddingVertical: spacing.md,
  },
  progressDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.hudBorder,
    marginHorizontal: 4,
  },
  progressDotActive: {
    backgroundColor: colors.primary,
    width: 24,
  },
  skipButton: {
    position: 'absolute',
    top: spacing.xl + 20,
    right: spacing.lg,
    zIndex: 1,
  },
  skipText: {
    ...typography.bodySmall,
    color: colors.textMuted,
  },
  content: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: spacing.xl,
  },
  stepIndicator: {
    flexDirection: 'row',
    marginBottom: spacing.xl,
  },
  stepDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: colors.hudBorder,
    marginHorizontal: 4,
  },
  stepDotActive: {
    backgroundColor: colors.primary,
    transform: [{ scale: 1.2 }],
  },
  stepDotComplete: {
    backgroundColor: colors.primary,
    opacity: 0.5,
  },
  iconContainer: {
    width: 120,
    height: 120,
    borderRadius: 60,
    backgroundColor: colors.bgSecondary,
    borderWidth: 2,
    borderColor: colors.hudBorder,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: spacing.xl,
  },
  icon: {
    fontSize: 56,
  },
  title: {
    ...typography.headingLarge,
    color: colors.textPrimary,
    textAlign: 'center',
    marginBottom: spacing.md,
  },
  description: {
    ...typography.bodyLarge,
    color: colors.textMuted,
    textAlign: 'center',
    lineHeight: 26,
    maxWidth: 300,
  },
  stepCount: {
    ...typography.labelSmall,
    color: colors.textMuted,
    marginTop: spacing.xl,
    letterSpacing: 2,
  },
  footer: {
    flexDirection: 'row',
    padding: spacing.lg,
    borderTopWidth: 1,
    borderTopColor: colors.hudBorder,
  },
  backButton: {
    flex: 0.4,
    marginRight: spacing.md,
  },
  continueButton: {
    flex: 0.6,
  },
});
