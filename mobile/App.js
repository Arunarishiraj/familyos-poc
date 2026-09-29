import React, { useEffect, useState } from "react";
import { View, Text, TextInput, Button, ScrollView, StyleSheet,
         ActivityIndicator, PermissionsAndroid, Platform } from "react-native";
import * as DocumentPicker from "expo-document-picker";
import * as Clipboard from "expo-clipboard";
import SmsAndroid from "react-native-get-sms-android";
import * as api from "./api";
import * as sync from "./sync";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function readInboxLastDays(days) {
  const minDate = Date.now() - days * 24 * 60 * 60 * 1000;
  const filter = { box: "inbox", minDate, maxCount: 500 };
  return new Promise((resolve, reject) => {
    SmsAndroid.list(
      JSON.stringify(filter),
      (fail) => reject(new Error(fail)),
      (count, smsList) => resolve(JSON.parse(smsList))
    );
  });
}

const fmtResults = (r) =>
  r.results.map((x) => `${x.file}: ${x.event} ${x.detail}`).join("\n") || "nothing sent";

function Login({ onDone }) {
  const [mode, setMode] = useState("login");
  const [f, setF] = useState({ name: "", email: "", password: "", invite: "" });
  const [err, setErr] = useState("");
  const set = (k) => (v) => setF({ ...f, [k]: v });
  const go = async () => {
    try {
      const r = mode === "login" ? await api.login(f) : await api.register(f);
      await api.setToken(r.token);
      onDone();
    } catch (e) { setErr(e.message); }
  };
  return (
    <View style={s.box}>
      <Text style={s.h}>FamilyOS</Text>
      {mode === "register" && (
        <TextInput style={s.input} placeholder="Name" onChangeText={set("name")} />)}
      <TextInput style={s.input} placeholder="Email" autoCapitalize="none"
                 keyboardType="email-address" onChangeText={set("email")} />
      <TextInput style={s.input} placeholder="Password (8+)" secureTextEntry
                 onChangeText={set("password")} />
      {mode === "register" && (
        <TextInput style={s.input} placeholder="Family invite code" autoCapitalize="none"
                   onChangeText={set("invite")} />)}
      <Button title={mode === "login" ? "Log in" : "Create account"} onPress={go} />
      <Button title={mode === "login" ? "New here? Register" : "Have an account? Log in"}
              onPress={() => setMode(mode === "login" ? "register" : "login")} />
      <Text style={s.err}>{err}</Text>
    </View>
  );
}

function Main({ onLogout }) {
  const [log, setLog] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const add = (t) => setLog((l) => t + "\n" + l);
  const run = async (fn) => {
    setBusy(true);
    try { await fn(); } catch (e) { add("Error: " + e.message); }
    setBusy(false);
  };

  const pickFiles = () => run(async () => {
    const r = await DocumentPicker.getDocumentAsync({
      multiple: true, copyToCacheDirectory: true,
      type: ["application/pdf", "text/plain", "message/rfc822", "text/calendar", "image/*"] });
    if (r.canceled) return;
    add(fmtResults(await api.ingest({ source: "Files",
      files: r.assets.map((a) => ({ uri: a.uri, name: a.name,
                                    type: a.mimeType || "application/octet-stream" })) })));
  });

  return (
    <ScrollView contentContainerStyle={s.box}>
      <Text style={s.h}>FamilyOS</Text>

      <Text style={s.sec}>1. Photos</Text>
      <Button title="Pick photos to send" disabled={busy}
              onPress={() => run(async () => add(`${await sync.pickAndSendPhotos(add)} photo(s) sent`))} />

      <Text style={s.sec}>2. Files and PDFs</Text>
      <Button title="Pick files" disabled={busy} onPress={pickFiles} />

      <Text style={s.sec}>3. Calendar (next 30 days)</Text>
      <Button title="Sync calendar" disabled={busy}
              onPress={() => run(async () => add(`${await sync.syncCalendar(add)} event(s) sent`))} />

      <Text style={s.sec}>4. Paste a message</Text>
      <TextInput style={[s.input, { minHeight: 70 }]} multiline value={message}
                 onChangeText={setMessage} placeholder="Copied SMS / chat text" />
      <Button title="Paste from clipboard" disabled={busy}
              onPress={() => run(async () => setMessage(await Clipboard.getStringAsync()))} />
      <Button title="Send text" disabled={busy || !message.trim()}
              onPress={() => run(async () => {
                add(fmtResults(await api.ingest({ source: "Pasted Text", message })));
                setMessage("");
              })} />

      <Text style={s.sec}>5. Process with Qwen</Text>
      <Button title="Run processing (Stage 4)" disabled={busy}
              onPress={() => run(async () => { await api.process(); add("Processing started on the server..."); })} />
      <Button title="Refresh results" disabled={busy}
              onPress={() => run(async () => {
                const rows = await api.artifacts();
                add(rows.map((r) => `${r.id} ${r.source}/${r.type} | ${r.doc_type || "-"} | ${r.title || "-"} | ${r.status}`).join("\n"));
              })} />

      <Text style={s.sec}>6. SMS (Android, last 7 days)</Text>
      <Button title="Read & categorize inbox SMS" disabled={busy || Platform.OS !== "android"}
              onPress={() => run(async () => {
                const granted = await PermissionsAndroid.request(
                  PermissionsAndroid.PERMISSIONS.READ_SMS,
                  { title: "SMS Access", message: "FamilyOS needs to read your SMS inbox.",
                    buttonPositive: "Allow" });
                if (granted !== PermissionsAndroid.RESULTS.GRANTED) {
                  add("Permission denied.");
                  return;
                }
                const raw = await readInboxLastDays(7);
                add(`Read ${raw.length} SMS from inbox.`);
                const messages = raw.map((m) => ({
                  id: String(m._id),
                  address: m.address || "",
                  body: m.body || "",
                  date: Math.floor(Number(m.date)),
                  direction: "received",
                }));
                const { job_id, total } = await api.smsCategorize(messages);
                add(`Job ${job_id} started for ${total} message(s)...`);
                let status;
                for (let i = 0; i < 60; i++) {
                  await sleep(2000);
                  status = await api.smsJobStatus(job_id);
                  if (status.status === "done" || status.status === "failed") break;
                  add(`...${status.done}/${status.total} processed`);
                }
                if (status.status === "failed") {
                  add(`Job failed: ${status.error}`);
                  return;
                }
                if (status.status !== "done") {
                  add("Job still running after timeout, check later.");
                  return;
                }
                add(`Done. Counts: ${JSON.stringify(status.counts)}`);
                const out = await api.smsOutput(status.file);
                add(out.messages.map((r) =>
                  `${r.address} | ${r.category} | ${r.suspicious ? "SUSPICIOUS" : "ok"} | ${r.summary}`
                ).join("\n"));
              })} />

      {busy && <ActivityIndicator style={{ marginTop: 10 }} />}
      <Text selectable style={s.log}>{log}</Text>
      <Button title="Log out" onPress={onLogout} />
    </ScrollView>
  );
}

export default function App() {
  const [ready, setReady] = useState(false);
  const [authed, setAuthed] = useState(false);
  useEffect(() => {
    api.setToken("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJNOUY1M0VCIiwiZmFtIjoiRjAwMSIsImV4cCI6MTc5MzI1MzUzMn0.Y0eVJgCjR_UtnGoZnxwHYH5ym7Q5wusBSv2mFRiBPOE").then(() => { setAuthed(true); setReady(true); }); // TEMP DEV BYPASS
  }, []);
  if (!ready) return <ActivityIndicator style={{ marginTop: 100 }} />;
  return authed
    ? <Main onLogout={async () => { await api.setToken(null); setAuthed(false); }} />
    : <Login onDone={() => setAuthed(true)} />;
}

const s = StyleSheet.create({
  box: { padding: 20, paddingTop: 60, gap: 8 },
  h: { fontSize: 26, fontWeight: "bold" },
  sec: { marginTop: 14, fontWeight: "bold", fontSize: 16 },
  input: { borderWidth: 1, borderColor: "#999", padding: 8, borderRadius: 4 },
  err: { color: "red" },
  log: { marginTop: 10, backgroundColor: "#eee", padding: 8 },
});
