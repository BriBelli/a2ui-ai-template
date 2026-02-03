
import './App.css';
import { useState } from 'react';
import { fetchOpenAI } from './services/openaiApi';

const App: React.FC = () => {
  const [prompt, setPrompt] = useState<string>("");
  const [response, setResponse] = useState<string>("");

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setResponse("Loading...");
    const result = await fetchOpenAI(prompt);
    setResponse(result);
  };

  return (
    <div>
      <h1>OpenAI Prompt</h1>
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Enter your prompt"
        />
        <button type="submit">Send</button>
      </form>
      <div>
        <strong>Response:</strong>
        <div>{response}</div>
      </div>
    </div>
  );
};

export default App;
