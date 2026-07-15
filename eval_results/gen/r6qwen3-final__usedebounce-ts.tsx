export function useDebouncedState<S>(
  value: S,
  ms = 300
): [S, (v: S) => void] {
  const [state, setState] = useState(value);
  useEffect(() => { let t; return () => clearTimeout(t); }, []);
  useEffect(
    () =>
      ((t = setTimeout(() => setState(value), ms)) as unknown),
    [ms, value]
  );
  return [state, setState];
}