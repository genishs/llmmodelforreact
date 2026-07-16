// .tsx에서 화살표 제네릭은 <T,>로 모호성 회피(<T>는 JSX로 오인됨)
const mapValues = <T, U>(obj: Record<string, T>, fn: (value: T) => U): Record<string, U> => {
  const result: Record<string, U> = {};
  for (const key in obj) {
    result[key] = fn(obj[key]);
  }
  return result;
};

export default mapValues;