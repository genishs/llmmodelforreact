import { useInfiniteQuery } from '@tanstack/react-query';
import axios from 'axios';

interface Product {
  id: number;
  name: string;
  price: number;
}

type Page = { products: Product[]; nextPage?: number };

async function fetchProducts(pageParam = 1): Promise<Page> {
  const res = await axios.get<{ products: Product[]; nextPage?: number }>(
    `/api/products?page=${pageParam}`
  );
  return res.data;
}

function ProductList() {
  const { data, isLoading, isError, hasNextPage, fetchNextPage } =
    useInfiniteQuery(['products'], fetchProducts, {
      getNextPageParam: (last) => last.nextPage,
    });

  if (isLoading) return <div>Loading...</div>;
  if (isError) return <div>Error :(</div>;

  return (
    <ul>
      {data.pages.map((p) =>
        p.products.map((product) => (
          <li key={product.id}>{product.name} (${product.price})</li>
        ))
      )}
      {hasNextPage && <button onClick={() => fetchNextPage()}>Load More</button>}
    </ul>
  );
}

export default ProductList;