/**
 * PROVENIQ Ops - Auth Store
 * User authentication state management
 */

import { create } from 'zustand';
import AsyncStorage from '@react-native-async-storage/async-storage';

export interface User {
  id: string;
  email: string;
  displayName: string;
  role: 'owner' | 'manager' | 'operator';
}

export type BusinessType = 'RESTAURANT' | 'RETAIL' | 'WAREHOUSE';

export interface Location {
  id: string;
  name: string;
  type: BusinessType;
  address?: string;
}

interface AuthStore {
  user: User | null;
  token: string | null;
  businessType: BusinessType | null;
  currentLocation: Location | null;
  locations: Location[];
  isLoading: boolean;
  isInitialized: boolean;
  isOnboarded: boolean;
  
  // Actions
  setUser: (user: User | null) => void;
  setToken: (token: string | null) => void;
  setBusinessType: (type: BusinessType) => void;
  setCurrentLocation: (location: Location | null) => void;
  setLocations: (locations: Location[]) => void;
  addLocation: (location: Omit<Location, 'id'>) => void;
  login: (email: string, password: string) => Promise<boolean>;
  logout: () => void;
  initialize: () => Promise<void>;
  completeOnboarding: () => void;
}

const STORAGE_KEYS = {
  USER: '@proveniq_ops_user',
  TOKEN: '@proveniq_ops_token',
  BUSINESS_TYPE: '@proveniq_ops_business_type',
  LOCATION: '@proveniq_ops_location',
  LOCATIONS: '@proveniq_ops_locations',
  ONBOARDED: '@proveniq_ops_onboarded',
};

export const useAuthStore = create<AuthStore>((set, get) => ({
  user: null,
  token: null,
  businessType: null,
  currentLocation: null,
  locations: [],
  isLoading: false,
  isInitialized: false,
  isOnboarded: false,
  
  setUser: (user) => set({ user }),
  setToken: (token) => set({ token }),
  
  setBusinessType: (type) => {
    set({ businessType: type });
    AsyncStorage.setItem(STORAGE_KEYS.BUSINESS_TYPE, type);
  },
  
  setCurrentLocation: (location) => {
    set({ currentLocation: location });
    if (location) {
      AsyncStorage.setItem(STORAGE_KEYS.LOCATION, JSON.stringify(location));
    } else {
      AsyncStorage.removeItem(STORAGE_KEYS.LOCATION);
    }
  },
  
  setLocations: (locations) => {
    set({ locations });
    AsyncStorage.setItem(STORAGE_KEYS.LOCATIONS, JSON.stringify(locations));
  },
  
  addLocation: (locationData) => {
    const { locations, businessType } = get();
    const newLocation: Location = {
      id: `loc_${Date.now()}`,
      ...locationData,
      type: locationData.type || businessType || 'RESTAURANT',
    };
    const updated = [...locations, newLocation];
    set({ locations: updated, currentLocation: newLocation });
    AsyncStorage.setItem(STORAGE_KEYS.LOCATIONS, JSON.stringify(updated));
    AsyncStorage.setItem(STORAGE_KEYS.LOCATION, JSON.stringify(newLocation));
  },
  
  completeOnboarding: () => {
    set({ isOnboarded: true });
    AsyncStorage.setItem(STORAGE_KEYS.ONBOARDED, 'true');
  },
  
  login: async (email, password) => {
    set({ isLoading: true });
    
    try {
      // TODO: Replace with actual Firebase auth
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      const mockUser: User = {
        id: 'user_001',
        email,
        displayName: email.split('@')[0],
        role: 'owner',
      };
      
      const mockToken = 'mock_token_' + Date.now();
      
      await AsyncStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(mockUser));
      await AsyncStorage.setItem(STORAGE_KEYS.TOKEN, mockToken);
      
      set({ 
        user: mockUser, 
        token: mockToken,
        isLoading: false,
      });
      
      return true;
    } catch (error) {
      set({ isLoading: false });
      return false;
    }
  },
  
  logout: async () => {
    await AsyncStorage.multiRemove(Object.values(STORAGE_KEYS));
    set({ 
      user: null, 
      token: null,
      businessType: null, 
      currentLocation: null,
      locations: [],
      isOnboarded: false,
    });
  },
  
  initialize: async () => {
    try {
      const [userJson, token, businessType, locationJson, locationsJson, onboarded] = await Promise.all([
        AsyncStorage.getItem(STORAGE_KEYS.USER),
        AsyncStorage.getItem(STORAGE_KEYS.TOKEN),
        AsyncStorage.getItem(STORAGE_KEYS.BUSINESS_TYPE),
        AsyncStorage.getItem(STORAGE_KEYS.LOCATION),
        AsyncStorage.getItem(STORAGE_KEYS.LOCATIONS),
        AsyncStorage.getItem(STORAGE_KEYS.ONBOARDED),
      ]);
      
      const user = userJson ? JSON.parse(userJson) : null;
      const currentLocation = locationJson ? JSON.parse(locationJson) : null;
      const locations = locationsJson ? JSON.parse(locationsJson) : [];
      
      set({ 
        user, 
        token, 
        businessType: businessType as BusinessType | null,
        currentLocation,
        locations,
        isOnboarded: onboarded === 'true',
        isInitialized: true,
      });
    } catch (error) {
      set({ isInitialized: true });
    }
  },
}));
