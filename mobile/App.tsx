/**
 * PROVENIQ Ops - Mobile Application
 * Synthetic Eye AR Inventory Scanner
 */

import { StatusBar } from 'expo-status-bar';
import { ScannerScreen } from './src/screens';

export default function App() {
  return (
    <>
      <StatusBar style="light" />
      <ScannerScreen />
    </>
  );
}
