import React from 'react';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { AuthProvider } from './src/contexts/AuthContext';
import { TradingProvider } from './src/contexts/TradingContext';
import { AppNavigator } from './src/navigation/AppNavigator';

export default function App() {
  return (
    <SafeAreaProvider>
      <AuthProvider>
        <TradingProvider>
          <StatusBar style="light" />
          <AppNavigator />
        </TradingProvider>
      </AuthProvider>
    </SafeAreaProvider>
  );
}
