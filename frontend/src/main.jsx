import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

function App() {
  const [status, setStatus] = useState('Comprobando…');
  const [astronaut, setAstronaut] = useState(null);
  const [message, setMessage] = useState('');
  const [reply, setReply] = useState('');
  const [error, setError] = useState('');
  const [provider, setProvider] = useState('Consultando…');
  const [usedProvider, setUsedProvider] = useState('');
  async function request(path, options) {
    const response = await fetch(path, options);
    if (!response.ok) throw new Error(`Error HTTP ${response.status}`);
    return response.json();
  }
  useEffect(() => { request('/api/health').then(() => setStatus('Conectado')).catch(() => setStatus('Sin conexión')); request('/api/apollo/config').then(data => setProvider(data.provider)).catch(() => setProvider('No disponible')); }, []);
  async function load() {
    try { setError(''); setAstronaut(await request('/api/astronauts/demo')); }
    catch { setError('No se pudieron cargar los indicadores.'); }
  }
  async function chat(event, override) {
    event?.preventDefault();
    try {
      setError(''); setReply(''); setUsedProvider('');
      const data = await request('/api/apollo/chat', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({message, ...(override ? {provider: override} : {})})});
      setReply(data.reply); setUsedProvider(data.mode);
    } catch { setError('No se pudo consultar a Apollo. Si Ollama no está disponible, puedes usar el modo determinista.'); }
  }
  return <main><header><p className="eyebrow">NASA SPACE APPS · PRUEBA DE CONCEPTO</p><h1>EIR</h1><p>Monitoreo de demostración para misiones espaciales.</p><p>Backend: <strong>{status}</strong></p></header>
    <section><h2>Indicadores del astronauta</h2><p>Datos sintéticos, sin uso clínico.</p><button onClick={load}>Consultar indicadores</button>{astronaut && <div className="metrics"><h3>{astronaut.name}</h3><p>Frecuencia cardíaca: {astronaut.heart_rate} lpm</p><p>Saturación de oxígeno: {astronaut.oxygen_saturation}%</p><p>Sueño: {astronaut.sleep_hours} horas</p></div>}</section>
    <section><h2>Apollo Mental</h2><p>Proveedor configurado: <strong>{provider}</strong></p><form onSubmit={chat}><label htmlFor="message">Tu mensaje</label><textarea id="message" value={message} onChange={e => setMessage(e.target.value)} required maxLength={1000} /><button type="submit">Consultar a Apollo</button></form>{error && <><p role="alert">{error}</p>{message.trim() && <button type="button" onClick={() => chat(null, 'deterministic')}>Usar respuesta determinista</button>}</>}{reply && <p role="status"><strong>Respuesta ({usedProvider}): </strong>{reply}</p>}</section></main>;
}

createRoot(document.getElementById('root')).render(<App />);
