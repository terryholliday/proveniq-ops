/**
 * PROVENIQ Ops - FAQ Screen
 * Frequently Asked Questions for users
 */

import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  SafeAreaView,
  ScrollView,
  TouchableOpacity,
} from 'react-native';
import { colors, typography, spacing } from '../theme';

interface FAQScreenProps {
  onBack: () => void;
}

interface FAQItem {
  id: string;
  category: string;
  question: string;
  answer: string;
}

const FAQ_DATA: FAQItem[] = [
  // Getting Started
  {
    id: '1',
    category: 'Getting Started',
    question: 'What is PROVENIQ Ops?',
    answer: 'PROVENIQ Ops is an inventory management system for restaurants, retail stores, and warehouses. It helps you scan inventory, detect shrinkage, and automatically reorder from vendors like SYSCO and US Foods.',
  },
  {
    id: '2',
    category: 'Getting Started',
    question: 'How do I set up my first location?',
    answer: 'During onboarding, you\'ll be asked to create your first location. Enter the name (e.g., "Main Kitchen") and address. You can add more locations later in Settings > Locations.',
  },
  {
    id: '3',
    category: 'Getting Started',
    question: 'What business types are supported?',
    answer: 'PROVENIQ Ops supports three business types:\n\n• Restaurant & Food Service - Kitchens, cafeterias, bars\n• Retail Store - Shops, boutiques, convenience stores\n• Warehouse & Distribution - Storage facilities, fulfillment',
  },

  // Scanning
  {
    id: '4',
    category: 'Scanning',
    question: 'How do I scan inventory?',
    answer: 'Tap "Scan Inventory" from the dashboard, then tap "BEGIN SCAN". Point your camera at items on the shelf. The app will automatically detect barcodes. When finished, tap "COMPLETE" to submit.',
  },
  {
    id: '5',
    category: 'Scanning',
    question: 'What if an item doesn\'t have a barcode?',
    answer: 'You can manually add items without barcodes. Go to Inventory > Add Item and enter the details manually. You can also take a photo for reference.',
  },
  {
    id: '6',
    category: 'Scanning',
    question: 'How accurate is the scanning?',
    answer: 'Barcode scanning is highly accurate (99%+). For best results, ensure good lighting and hold the camera steady about 6-12 inches from the barcode.',
  },

  // Par Levels & Ordering
  {
    id: '7',
    category: 'Ordering',
    question: 'What are par levels?',
    answer: 'Par levels are minimum stock quantities. When inventory falls below par, the system creates reorder suggestions. Example: par level of 10 gallons milk, you have 3 = alert triggered.',
  },
  {
    id: '8',
    category: 'Ordering',
    question: 'How does auto-ordering work?',
    answer: 'When items fall below par level, a draft order is created.\n\n• Operators - Orders need Manager approval\n• Managers - Can approve up to set limit\n• Owners - Can auto-approve all orders',
  },
  {
    id: '9',
    category: 'Ordering',
    question: 'Can I set spending limits?',
    answer: 'Yes. Go to Settings > Order Limits. Set daily limits, per-order maximum, and auto-approve threshold.',
  },

  // Vendors
  {
    id: '10',
    category: 'Vendors',
    question: 'Which vendors are supported?',
    answer: 'Currently supported:\n\n• SYSCO\n• US Foods\n• Performance Food Group (PFG)\n• Gordon Food Service (GFS)\n\nYou can also add custom vendors.',
  },
  {
    id: '11',
    category: 'Vendors',
    question: 'How do I connect my vendor account?',
    answer: 'Go to Settings > Vendors > select vendor > Connect Account. You\'ll need your customer number and API credentials. Contact your vendor rep if needed.',
  },

  // Team & Roles
  {
    id: '12',
    category: 'Team',
    question: 'What are the different user roles?',
    answer: '• Owner - Full control, billing, delete business\n• Manager - Manage team, approve orders, edit par levels\n• Operator - Scan inventory, create orders (needs approval)\n• Viewer - Read-only access to reports',
  },
  {
    id: '13',
    category: 'Team',
    question: 'How do I invite team members?',
    answer: 'Go to Settings > Team > Invite Member. Enter their email and select a role. They\'ll receive an invitation to join.',
  },

  // Shrinkage
  {
    id: '14',
    category: 'Shrinkage',
    question: 'What is shrinkage?',
    answer: 'Shrinkage is inventory loss from theft, spoilage, damage, or errors. PROVENIQ detects it by comparing expected vs actual counts.',
  },
  {
    id: '15',
    category: 'Shrinkage',
    question: 'How do I report shrinkage?',
    answer: 'When scanning reveals a discrepancy, classify it as:\n\n• Theft\n• Spoilage\n• Damage\n• Admin Error\n• Vendor Error\n• Unknown',
  },

  // Predictions & Alerts
  {
    id: '18',
    category: 'Predictions',
    question: 'What is burn rate?',
    answer: 'Burn rate is how fast you use inventory. The system calculates it from scan history:\n\n• 7-day average\n• 30-day average\n• 90-day average\n\nThis predicts when you\'ll run out.',
  },
  {
    id: '19',
    category: 'Predictions',
    question: 'How do stockout predictions work?',
    answer: 'The system predicts when items will run out based on:\n\n• Current quantity\n• Your burn rate\n• Pending orders\n\nRisk levels: Low (72+ hours), Medium (24-72h), High (12-24h), Critical (<12h).',
  },
  {
    id: '20',
    category: 'Predictions',
    question: 'What do the action recommendations mean?',
    answer: '• None - Stock is healthy\n• Monitor - Watch this item\n• Order Soon - Place order within 24h\n• Order Now - Order immediately\n• Emergency - Stockout imminent, expedite order',
  },
  {
    id: '21',
    category: 'Predictions',
    question: 'How accurate are predictions?',
    answer: 'Accuracy depends on data:\n\n• New items: 50-60% confidence\n• 7+ days of scans: 70-80%\n• 30+ days: 85-90%\n\nScan regularly for better predictions.',
  },

  // Troubleshooting
  {
    id: '16',
    category: 'Troubleshooting',
    question: 'Camera won\'t scan barcodes',
    answer: '1. Check camera permission in device settings\n2. Clean camera lens\n3. Improve lighting\n4. Hold steady 6-12 inches away\n5. Try landscape for long barcodes',
  },
  {
    id: '17',
    category: 'Troubleshooting',
    question: 'How do I contact support?',
    answer: 'Email: support@proveniq.io\n\nInclude your business name, issue description, and screenshots. We respond within 24 hours.',
  },
];

const CATEGORIES = [...new Set(FAQ_DATA.map(item => item.category))];

export function FAQScreen({ onBack }: FAQScreenProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  const filteredFAQ = selectedCategory 
    ? FAQ_DATA.filter(item => item.category === selectedCategory)
    : FAQ_DATA;

  const toggleExpand = (id: string) => {
    setExpandedId(expandedId === id ? null : id);
  };

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={onBack} style={styles.backButton}>
          <Text style={styles.backText}>← BACK</Text>
        </TouchableOpacity>
        <Text style={styles.title}>FAQ</Text>
        <View style={styles.placeholder} />
      </View>

      {/* Category Filter */}
      <ScrollView 
        horizontal 
        showsHorizontalScrollIndicator={false}
        style={styles.categoryScroll}
        contentContainerStyle={styles.categoryContainer}
      >
        <TouchableOpacity
          style={[styles.categoryPill, !selectedCategory && styles.categoryPillActive]}
          onPress={() => setSelectedCategory(null)}
        >
          <Text style={[styles.categoryText, !selectedCategory && styles.categoryTextActive]}>
            All
          </Text>
        </TouchableOpacity>
        {CATEGORIES.map((category) => (
          <TouchableOpacity
            key={category}
            style={[styles.categoryPill, selectedCategory === category && styles.categoryPillActive]}
            onPress={() => setSelectedCategory(category)}
          >
            <Text style={[styles.categoryText, selectedCategory === category && styles.categoryTextActive]}>
              {category}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {/* FAQ List */}
      <ScrollView style={styles.content} contentContainerStyle={styles.scrollContent}>
        {filteredFAQ.map((item) => (
          <TouchableOpacity
            key={item.id}
            style={styles.faqItem}
            onPress={() => toggleExpand(item.id)}
            activeOpacity={0.7}
          >
            <View style={styles.faqHeader}>
              <Text style={styles.faqQuestion}>{item.question}</Text>
              <Text style={styles.faqExpand}>{expandedId === item.id ? '−' : '+'}</Text>
            </View>
            {expandedId === item.id && (
              <Text style={styles.faqAnswer}>{item.answer}</Text>
            )}
          </TouchableOpacity>
        ))}

        {/* Contact Support */}
        <View style={styles.supportSection}>
          <Text style={styles.supportTitle}>Still have questions?</Text>
          <Text style={styles.supportText}>
            Contact support@proveniq.io
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bgPrimary,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.hudBorder,
  },
  backButton: {
    padding: spacing.sm,
  },
  backText: {
    ...typography.labelSmall,
    color: colors.primary,
    letterSpacing: 1,
  },
  title: {
    ...typography.labelMedium,
    color: colors.textPrimary,
    letterSpacing: 2,
  },
  placeholder: {
    width: 60,
  },
  categoryScroll: {
    maxHeight: 50,
    borderBottomWidth: 1,
    borderBottomColor: colors.hudBorder,
  },
  categoryContainer: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    gap: spacing.sm,
    flexDirection: 'row',
  },
  categoryPill: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.hudBorder,
  },
  categoryPillActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  categoryText: {
    ...typography.bodySmall,
    color: colors.textSecondary,
  },
  categoryTextActive: {
    color: colors.bgPrimary,
    fontWeight: '600',
  },
  content: {
    flex: 1,
  },
  scrollContent: {
    padding: spacing.md,
    paddingBottom: spacing.xl,
  },
  faqItem: {
    backgroundColor: colors.bgSecondary,
    borderWidth: 1,
    borderColor: colors.hudBorder,
    borderRadius: 8,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  faqHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  faqQuestion: {
    ...typography.bodyMedium,
    color: colors.textPrimary,
    fontWeight: '600',
    flex: 1,
    marginRight: spacing.sm,
  },
  faqExpand: {
    fontSize: 20,
    color: colors.primary,
    fontWeight: 'bold',
  },
  faqAnswer: {
    ...typography.bodyMedium,
    color: colors.textSecondary,
    marginTop: spacing.md,
    lineHeight: 22,
  },
  supportSection: {
    alignItems: 'center',
    padding: spacing.xl,
    marginTop: spacing.lg,
  },
  supportTitle: {
    ...typography.bodyLarge,
    color: colors.textPrimary,
    fontWeight: '600',
    marginBottom: spacing.xs,
  },
  supportText: {
    ...typography.bodyMedium,
    color: colors.primary,
  },
});
