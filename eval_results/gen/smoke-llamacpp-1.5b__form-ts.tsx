import React from 'react';

interface FormState {
  username: string;
  password: string;
}

const Login: React.FC = () => {
  const [state, setState] = React.useState<FormState>({
    username: '',
    password: ''
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setState({
      ...state,
      [e.target.name]: e.target.value
    });
  };

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    // Add your login logic here
    console.log('Username:', state.username);
    console.log('Password:', state.password);
  };

  return (
    <form onSubmit={handleSubmit}>
      <label>
        Username:
        <input type="text" name="username" value={state.username} onChange={handleChange} />
      </label>
      <br />
      <label>
        Password:
        <input type="password" name="password" value={state.password} onChange={handleChange} />
      </label>
      <br />
      <button type="submit">Login</button>
    </form>
  );
};

export default Login;