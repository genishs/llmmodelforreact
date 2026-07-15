import React from 'react';

interface Props {
  pagination?: { currentPageNo: number; totalRecordCount: number; recordCountPerPage: number; pageSize: number };
  moveToPage: (pageNo: number) => void;
}

function EgovPaging({ pagination, moveToPage }: Props) {
  console.groupCollapsed('EgovPaging');
  console.log('EgovPaging [props] : ', { pagination, moveToPage });

  let paginationTag: JSX.Element[] = [];

  const currentPageNo = pagination?.currentPageNo ?? 1;
  const totalRecordCount = pagination?.totalRecordCount ?? 0;
  const recordCountPerPage = pagination?.recordCountPerPage ?? 10;
  const pageSize = pagination?.pageSize ?? 10;
  const totalPageCount = Math.ceil(totalRecordCount / recordCountPerPage);

  if (pagination === undefined) {
    paginationTag = <span>-</span>;
  } else {
    const currentFirstPage = Math.floor((currentPageNo - 1) / pageSize) * pageSize + 1;
    let currentLastPage = currentFirstPage + pageSize - 1;
    currentLastPage = currentLastPage > totalPageCount ? totalPageCount : currentLastPage;

    for (let i = currentFirstPage; i <= currentLastPage; i++) {
      if (i === currentPageNo) {
        paginationTag.push(<span key={i} className="num_on">{i}</span>);
      } else {
        paginationTag.push(
          <button key={i} onClick={() => moveToPage(i)} className="num_off">{i}</button>
        );
      }
    }
  }

  console.log('paginationTag', paginationTag);
  console.groupEnd('EgovPaging');

  return (
    <div className="num_wrap d_flex d_jcc aic">
      <button className="num_l img_all" onClick={() => { if (currentPageNo > 1) moveToPage(currentPageNo - 1); }} style={{ opacity: currentPageNo > 1 ? 1 : 0.5 }} tabIndex={0}>◀️</button>
      {paginationTag}
      <button className="num_r img_all" onClick={() => { if (currentPageNo < totalPageCount) moveToPage(currentPageNo + 1); }} style={{ opacity: currentPageNo < totalPageCount ? 1 : 0.5 }} tabIndex={0}>▶️</button>
    </div>
  );
}

export default EgovPaging;