import * as SecureStore from "expo-secure-store";
import { API_URL } from "./config";

let token = null;

export async function loadToken() {
  try { token = await SecureStore.getItemAsync("token"); } catch (e) { token = null; }
  return token;
}
export async function setToken(t) {
  token = t;
  try {
    if (t) await SecureStore.setItemAsync("token", t);
    else await SecureStore.deleteItemAsync("token");
  } catch (e) {}
}

async function req(path, opts = {}) {
  const res = await fetch(API_URL + path, {
    ...opts,
    headers: { ...(token ? { Authorization: "Bearer " + token } : {}),
               ...(opts.headers || {}) },
  });
  if (!res.ok) {
    let d = "";
    try { d = (await res.json()).detail; } catch (e) {}
    throw new Error(`HTTP ${res.status} ${d}`);
  }
  return res.json();
}

const json = (body) => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const register = (b) => req("/auth/register", json(b));
export const login = (b) => req("/auth/login", json(b));
export const known = (source) => req("/api/sync/known?source=" + encodeURIComponent(source));
export const process = () => req("/api/process", { method: "POST" });
export const artifacts = () => req("/api/artifacts");

export function ingest({ source, files = [], message = "", refs = [] }) {
  const f = new FormData();
  f.append("source_system", source);
  f.append("message", message);
  f.append("refs", JSON.stringify(refs));
  files.forEach((x) => f.append("files", x));
  return req("/api/ingest", { method: "POST", body: f });
}

export const ingestText = (source, items) =>
  req("/api/ingest_text", json({ source_system: source, items }));

export const smsCategorize = (messages) => req("/api/sms/categorize", json({ messages }));
export const smsJobStatus = (jobId) => req("/api/sms/job/" + jobId);
export const smsOutput = (name) => req("/api/sms/outputs/" + name);
