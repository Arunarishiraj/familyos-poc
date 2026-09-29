import * as ImagePicker from "expo-image-picker";
import * as Calendar from "expo-calendar";
import * as api from "./api";

const chunk = (arr, n) =>
  Array.from({ length: Math.ceil(arr.length / n) }, (_, i) => arr.slice(i * n, i * n + n));

// Photos: the user picks which ones to send (compressed to JPEG by the picker)
export async function pickAndSendPhotos(log) {
  const r = await ImagePicker.launchImageLibraryAsync({
    mediaTypes: ["images"], allowsMultipleSelection: true, quality: 0.6,
  });
  if (r.canceled) return 0;
  const files = r.assets.map((a, i) => ({
    uri: a.uri, type: a.mimeType || "image/jpeg",
    name: (a.fileName || `photo_${Date.now()}_${i}`).replace(/\.[^.]+$/, "") + ".jpg",
  }));
  let done = 0;
  for (const group of chunk(files, 2)) {
    const res = await api.ingest({ source: "Photos", files: group });
    res.results.forEach((x) => log(`${x.file}: ${x.event} ${x.detail}`));
    done += group.length;
  }
  return done;
}

// Calendar: each event becomes a tiny .ics file
const fmt = (d) => new Date(d).toISOString().replace(/[-:]/g, "").replace(/\.\d+/, "");
const one = (s) => (s || "").replace(/[\r\n]+/g, " ");

export async function syncCalendar(log, days = 30) {
  const p = await Calendar.requestCalendarPermissionsAsync();
  if (p.status !== "granted") throw new Error("Calendar permission denied");
  const cals = await Calendar.getCalendarsAsync(Calendar.EntityTypes.EVENT);
  const events = await Calendar.getEventsAsync(
    cals.map((c) => c.id), new Date(), new Date(Date.now() + days * 864e5));
  const known = new Set(await api.known("Calendar"));
  const items = events
    .map((e) => ({
      ref: `${e.id}|${fmt(e.startDate)}`,
      name: `event_${e.id}`.replace(/[^A-Za-z0-9_]/g, ""),
      kind: "ics",
      content: ["BEGIN:VCALENDAR", "VERSION:2.0", "BEGIN:VEVENT",
        `SUMMARY:${one(e.title)}`, `DTSTART:${fmt(e.startDate)}`,
        `DTEND:${fmt(e.endDate)}`, `LOCATION:${one(e.location)}`,
        `DESCRIPTION:${one(e.notes)}`, "END:VEVENT", "END:VCALENDAR"].join("\n"),
    }))
    .filter((x) => !known.has(x.ref));
  log(`${items.length} new events in the next ${days} days`);
  for (const group of chunk(items, 5)) {
    await api.ingestText("Calendar", group);
  }
  return items.length;
}
