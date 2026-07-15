import React from 'react';

interface PaginationProps {
  pagination?: {
    currentPageNo?: number;
    totalRecordCount?: number;
    recordCountPerPage?: number;
    pageSize?: number;
  };
  moveToPage: (page: number) => void;
}

const EgovPaging: React.FC<PaginationProps> = ({ pagination, moveToPage }) => {
  console.groupCollapsed('EgovPaging');
  console.log('EgovPaging [props]:', { pagination });

  const { currentPageNo = 1, totalRecordCount = 0, recordCountPerPage = 10, pageSize = 10 } = pagination ?? {};
  const totalPageCount = Math.ceil(totalRecordCount / recordCountPerPage);
  const currentFirstPage = Math.floor((currentPageNo - 1) / pageSize) * pageSize + 1;
  const currentLastPage = Math.min(currentFirstPage + pageSize - 1, totalPageCount);
  const paginationTag = Array.from({ length: currentLastPage - currentFirstPage + 1 }, (_, i) =>
    i + currentFirstPage === currentPageNo ?
      (<div key={i}><button className="num_on"><div className="num_on1" />{i + currentFirstPage}</button></div>) :
      (<div key={i}><button className="num_off" onClick={() => moveToPage(i + currentFirstPage)}>{i + currentFirstPage}</button></div>)
  );

  console.log('paginationTag:', paginationTag);
  console.groupEnd();

  return (
    <div className="num_wrap d_flex d_jcc aic">
      <button className="num_l img_all" onClick={() => currentPageNo > 1 && moveToPage(currentPageNo - 1)}
        style={{ opacity: currentPageNo > 1 ? 1 : 0.5 }} aria-label="이전 페이지">◀</button>
      {paginationTag}
      <button className="num_r img_all" onClick={() => currentPageNo < totalPageCount && moveToPage(currentPageNo + 1)}
        style={{ opacity: currentPageNo < totalPageCount ? 1 : 0.5 }} aria-label="다음 페이지">▶</button>
    </div>
  );
};

export default EgovPaging;