import React from 'react';

interface Props {
  pagination?: { currentPageNo: number; totalRecordCount: number; recordCountPerPage: number; pageSize: number };
  moveToPage: (pageNo: number) => void;
}

function EgovPaging({ pagination, moveToPage }: Props) {
  const currentPageNo = pagination?.currentPageNo ?? 1;
  const totalRecordCount = pagination?.totalRecordCount ?? 0;
  const recordCountPerPage = pagination?.recordCountPerPage ?? 10;
  const pageSize = pagination?.pageSize ?? 10;
  const totalPageCount = Math.ceil(totalRecordCount / recordCountPerPage);

  if (!pagination) return <span>-</span>;

  const currentFirstPage = Math.floor((currentPageNo - 1) / pageSize) * pageSize + 1;
  const currentLastPage = Math.min(currentFirstPage + pageSize - 1, totalPageCount);
  const pages = Array.from({ length: currentLastPage - currentFirstPage + 1 }, (_, i) => currentFirstPage + i);

  return (
    <div className="num_wrap d_flex d_jcc aic">
      <button className="num_l img_all" onClick={() => currentPageNo > 1 && moveToPage(currentPageNo - 1)} style={{ opacity: currentPageNo > 1 ? 1 : 0.5 }} tabIndex="0">◀️</button>
      {pages.map(page => <button key={page} className={`num${page === currentPageNo ? '_on' : ''}`} onClick={() => moveToPage(page)}>{page}</button>)}
      <button className="num_r img_all" onClick={() => currentPageNo < totalPageCount && moveToPage(currentPageNo + 1)} style={{ opacity: currentPageNo < totalPageCount ? 1 : 0.5 }} tabIndex="0">▶️</button>
    </div>
  );
}

export default EgovPaging;