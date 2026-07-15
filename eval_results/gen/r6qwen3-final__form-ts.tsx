import { useState } from 'react';

interface FormState {
  email: string;
  password: string;
}

function LoginForm() {
  const [state, setState] = useState<FormState>({ email: '', password: '' });

  const handleChange =
    <K extends keyof FormState>(k: K) =>
    ({ target }: React.ChangeEvent<HTMLInputElement>) => {
      setState((s) => ({ ...s, [k]: target.value }));
    };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    try {
      await fetch('/api/login', { method: 'POST', body: JSON.stringify(state), headers: { 'Content-Type': 'application/json' } });
      alert('Logged in!');
    } catch { alert('Login failed'); }
  };

  return (
    <form onSubmit={handleSubmit}>
      <input value={state.email} onChange={handleChange('email')} placeholder="Email" required />
      <input type="password" value={state.password} onChange={handleChange('password')} placeholder="Password" required />
      <button type="submit">Log In</button>
    </form>
  );
}

export default LoginForm;