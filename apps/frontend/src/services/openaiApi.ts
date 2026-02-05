export async function fetchOpenAI(prompt: string): Promise<string> {
  try {
    const res = await fetch("/api/openai", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt }),
    });
    const data = await res.json();
    return data.response || data.error;
  } catch (err: any) {
    return "Error: " + err.message;
  }
}
