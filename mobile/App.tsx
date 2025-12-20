/**
 * PROVENIQ Ops - Mobile Application
 * Inventory Operations for Restaurants & Retail
 */

import React, { useEffect, useState } from 'react';
import { View, ActivityIndicator, StyleSheet, Text } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { 
  ScannerScreen, 
  LoginScreen, 
  SettingsScreen,
  BusinessTypeScreen,
  HomeScreen,
  WelcomeScreen,
  BusinessInfoScreen,
  LocationSetupScreen,
  VendorSetupScreen,
  TeamInviteScreen,
  TutorialScreen,
  ReadyScreen,
  FAQScreen,
} from './src/screens';
import type { 
  BusinessInfoData, 
  LocationData, 
  VendorSelection, 
  TeamInvite 
} from './src/screens';
import { useAuthStore } from './src/store';

type Screen = 
  | 'loading' 
  | 'login' 
  // Onboarding
  | 'onboarding_welcome'
  | 'onboarding_business_info'
  | 'onboarding_business_type'
  | 'onboarding_location'
  | 'onboarding_vendors'
  | 'onboarding_team'
  | 'onboarding_tutorial'
  | 'onboarding_ready'
  // Main app
  | 'home'
  | 'scan' 
  | 'inventory'
  | 'orders'
  | 'alerts'
  | 'settings'
  | 'faq';

// Temporary storage for onboarding data
interface OnboardingData {
  businessInfo?: BusinessInfoData;
  locationData?: LocationData;
  vendors?: VendorSelection[];
  teamInvites?: TeamInvite[];
}

export default function App() {
  const [currentScreen, setCurrentScreen] = useState<Screen>('loading');
  const [onboardingData, setOnboardingData] = useState<OnboardingData>({});
  
  const { 
    user, 
    businessType,
    currentLocation, 
    isInitialized, 
    isOnboarded,
    initialize,
    setBusinessType,
    addLocation,
    completeOnboarding,
  } = useAuthStore();

  useEffect(() => {
    initialize();
  }, []);

  // Determine initial screen based on auth/onboarding state
  useEffect(() => {
    if (!isInitialized) {
      setCurrentScreen('loading');
    } else if (!user) {
      setCurrentScreen('login');
    } else if (!isOnboarded) {
      setCurrentScreen('onboarding_welcome');
    } else {
      setCurrentScreen('home');
    }
  }, [isInitialized, user, isOnboarded]);

  const handleNavigate = (screen: string) => {
    setCurrentScreen(screen as Screen);
  };

  // Complete onboarding and save all data
  const finishOnboarding = () => {
    // Save location
    if (onboardingData.locationData && businessType) {
      const fullAddress = [
        onboardingData.locationData.address,
        onboardingData.locationData.city,
        onboardingData.locationData.state,
        onboardingData.locationData.zipCode,
      ].filter(Boolean).join(', ');

      addLocation({
        name: onboardingData.locationData.name,
        address: fullAddress || undefined,
        type: businessType,
      });
    }

    // TODO: Save vendors to backend
    // TODO: Send team invites via backend

    completeOnboarding();
    setCurrentScreen('home');
  };

  // Loading screen
  if (currentScreen === 'loading') {
    return (
      <View style={styles.loading}>
        <StatusBar style="light" />
        <Text style={styles.loadingLogo}>PROVENIQ OPS</Text>
        <ActivityIndicator size="large" color="#00b4d8" style={styles.spinner} />
      </View>
    );
  }

  // Login screen
  if (currentScreen === 'login') {
    return (
      <>
        <StatusBar style="light" />
        <LoginScreen onLoginSuccess={() => setCurrentScreen('onboarding_welcome')} />
      </>
    );
  }

  // ============ ONBOARDING FLOW ============

  // Step 0: Welcome
  if (currentScreen === 'onboarding_welcome') {
    return (
      <>
        <StatusBar style="light" />
        <WelcomeScreen 
          onContinue={() => setCurrentScreen('onboarding_business_info')} 
        />
      </>
    );
  }

  // Step 1: Business Info
  if (currentScreen === 'onboarding_business_info') {
    return (
      <>
        <StatusBar style="light" />
        <BusinessInfoScreen
          onContinue={(data) => {
            setOnboardingData(prev => ({ ...prev, businessInfo: data }));
            setCurrentScreen('onboarding_business_type');
          }}
          onBack={() => setCurrentScreen('onboarding_welcome')}
        />
      </>
    );
  }

  // Step 2: Business Type
  if (currentScreen === 'onboarding_business_type') {
    return (
      <>
        <StatusBar style="light" />
        <BusinessTypeScreen 
          onTypeSelected={() => setCurrentScreen('onboarding_location')} 
        />
      </>
    );
  }

  // Step 3: Location Setup
  if (currentScreen === 'onboarding_location') {
    return (
      <>
        <StatusBar style="light" />
        <LocationSetupScreen
          businessType={businessType || 'RESTAURANT'}
          onContinue={(data) => {
            setOnboardingData(prev => ({ ...prev, locationData: data }));
            setCurrentScreen('onboarding_vendors');
          }}
          onBack={() => setCurrentScreen('onboarding_business_type')}
        />
      </>
    );
  }

  // Step 4: Vendor Setup (Optional)
  if (currentScreen === 'onboarding_vendors') {
    return (
      <>
        <StatusBar style="light" />
        <VendorSetupScreen
          onContinue={(vendors) => {
            setOnboardingData(prev => ({ ...prev, vendors }));
            setCurrentScreen('onboarding_team');
          }}
          onSkip={() => setCurrentScreen('onboarding_team')}
          onBack={() => setCurrentScreen('onboarding_location')}
        />
      </>
    );
  }

  // Step 5: Team Invite (Optional)
  if (currentScreen === 'onboarding_team') {
    return (
      <>
        <StatusBar style="light" />
        <TeamInviteScreen
          onContinue={(invites) => {
            setOnboardingData(prev => ({ ...prev, teamInvites: invites }));
            setCurrentScreen('onboarding_tutorial');
          }}
          onSkip={() => setCurrentScreen('onboarding_tutorial')}
          onBack={() => setCurrentScreen('onboarding_vendors')}
        />
      </>
    );
  }

  // Step 6: Tutorial (Optional)
  if (currentScreen === 'onboarding_tutorial') {
    return (
      <>
        <StatusBar style="light" />
        <TutorialScreen
          onContinue={() => setCurrentScreen('onboarding_ready')}
          onSkip={() => setCurrentScreen('onboarding_ready')}
          onBack={() => setCurrentScreen('onboarding_team')}
        />
      </>
    );
  }

  // Step 7: Ready
  if (currentScreen === 'onboarding_ready') {
    return (
      <>
        <StatusBar style="light" />
        <ReadyScreen
          businessName={onboardingData.businessInfo?.businessName || 'Your Business'}
          locationName={onboardingData.locationData?.name || 'Main Location'}
          vendorCount={onboardingData.vendors?.length || 0}
          teamCount={onboardingData.teamInvites?.length || 0}
          onFinish={finishOnboarding}
        />
      </>
    );
  }

  // ============ MAIN APP ============

  // Settings screen
  if (currentScreen === 'settings') {
    return (
      <>
        <StatusBar style="light" />
        <SettingsScreen 
          onBack={() => setCurrentScreen('home')} 
          onOpenFAQ={() => setCurrentScreen('faq')}
        />
      </>
    );
  }

  // FAQ screen
  if (currentScreen === 'faq') {
    return (
      <>
        <StatusBar style="light" />
        <FAQScreen onBack={() => setCurrentScreen('settings')} />
      </>
    );
  }

  // Scanner screen
  if (currentScreen === 'scan') {
    return (
      <>
        <StatusBar style="light" />
        <ScannerScreen onOpenSettings={() => setCurrentScreen('settings')} />
      </>
    );
  }

  // Placeholder screens (to be built)
  if (currentScreen === 'inventory' || currentScreen === 'orders' || currentScreen === 'alerts') {
    return (
      <>
        <StatusBar style="light" />
        <HomeScreen onNavigate={handleNavigate} />
      </>
    );
  }

  // Home screen (main app hub)
  return (
    <>
      <StatusBar style="light" />
      <HomeScreen onNavigate={handleNavigate} />
    </>
  );
}

const styles = StyleSheet.create({
  loading: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#0a0a0f',
  },
  loadingLogo: {
    color: '#00b4d8',
    fontSize: 18,
    letterSpacing: 4,
    marginBottom: 20,
  },
  spinner: {
    marginTop: 10,
  },
});
