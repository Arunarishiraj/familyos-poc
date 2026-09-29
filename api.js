
export const smsCategorize = (messages) => req("/api/sms/categorize", json({ messages }));
export const smsJobStatus = (jobId) => req("/api/sms/job/" + jobId);
export const smsOutput = (name) => req("/api/sms/outputs/" + name);
