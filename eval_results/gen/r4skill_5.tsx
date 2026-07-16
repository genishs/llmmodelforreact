import { useState, useCallback } from 'react';

type AsyncState<T> =
  | { status: 'idle' }
  | { status: 'pending' }
  | { status: 'error'; error: Error }
  | { status: 'success'; data: T };

function useAsync<T>(fn: () => Promise<T>) {
  const [state, setState] = useState<AsyncState<T>>({ status: 'idle' });
  const run = useCallback(async () => {
    setState({ status: 'pending' });
    try {
      const data = await fn();
      setState({ status: 'success', data });
    } catch (e) {
      setState({ status: 'error', error: e as Error });
    }
  }, [fn]);
  return { state, run };
}

export default useAsync;