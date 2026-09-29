import React, { useState } from 'react';
import { View, Text, Button, FlatList, PermissionsAndroid, Platform, ActivityIndicator } from 'react-native';
import SmsAndroid from 'react-native-get-sms-android';

const API_BASE = 'http://<your-codespace-public-url>:8000'; // update per session

export default function SmsInboxScreen({ token }) {
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);

  async function requestPermission() {
    if (Platform.OS !== 'android') {
      setError('SMS reading only works on Android.');
      return false;
    }
    const granted = await PermissionsAndroid.request(
      PermissionsAndroid.PERMISSIONS.READ_SMS,
      {
        title: 'SMS Access',
        message: 'FamilyOS needs to read your SMS inbox to categorize messages.',
        buttonPositive: 'Allow',
      }
    );
    return granted === PermissionsAndroid.RESULTS.GRANTED;
  }

  function readInboxLastWeek() {
    const oneWeekAgo = Date.now() - 7 * 24 * 60 * 60 * 1000;

    const filter = {
      box: 'inbox',
      minDate: oneWeekAgo,
      maxCount: 500,
    };

    return new Promise((resolve, reject) => {
      SmsAndroid.list(
        JSON.stringify(filter),
        (fail) => reject(new Error(fail)),
        (count, smsList) => resolve(JSON.parse(smsList))
      );
    });
  }

  async function handleReadAndCategorize() {
    setError(null);
    setLoading(true);
    try {
      const ok = await requestPermission();
      if (!ok) {
        setError('Permission denied.');
        setLoading(false);
        return;
      }

      const messages = await readInboxLastWeek();

      const payload = messages.map((m) => ({
        id: String(m._id),
        direction: 'received',
        address: m.address,
        date: new Date(Number(m.date)).toISOString(),
        body: m.body,
      }));

      const res = await fetch(`${API_BASE}/api/sms/categorize`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ messages: payload, window_days: 7 }),
      });

      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      const data = await res.json();
      setResults(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <View style={{ flex: 1, padding: 16 }}>
      <Button title="Read & Categorize Last 7 Days of SMS" onPress={handleReadAndCategorize} />
      {loading && <ActivityIndicator style={{ marginTop: 12 }} />}
      {error && <Text style={{ color: 'red', marginTop: 12 }}>{error}</Text>}
      {results && (
        <FlatList
          style={{ marginTop: 16 }}
          data={results.messages}
          keyExtractor={(item) => item.id}
          renderItem={({ item }) => (
            <View style={{ paddingVertical: 8, borderBottomWidth: 1, borderColor: '#eee' }}>
              <Text style={{ fontWeight: 'bold' }}>{item.address} — {item.category}</Text>
              <Text numberOfLines={2}>{item.body}</Text>
              {item.suspicious && <Text style={{ color: 'red' }}>⚠ Flagged suspicious</Text>}
            </View>
          )}
        />
      )}
    </View>
  );
}
