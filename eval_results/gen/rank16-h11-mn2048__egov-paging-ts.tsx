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
  const currentFirstPage = Math.floor((currentPageNo - 1) / pageSize) * pageSize + 1;
  const currentLastPage = Math.min(currentFirstPage + pageSize - 1, totalPageCount);
  const paginationTag = Array.from({ length: currentLastPage - currentFirstPage + 1 }, (_, i) => (
    <div key={currentFirstPage + i}>
      <button className={`num_${currentPageNo === currentFirstPage + i ? 'on' : 'off'}`}
        onClick={() => moveToPage(currentFirstPage + i)}
        tabIndex="0">{currentFirstPage + i}</button>
    </div>
  ));
  return (
    <div className="num_wrap d_flex d_jcc aic">
      <button className="num_l img_all" onClick={() => currentPageNo > 1 && moveToPage(currentPageNo - 1)} tabIndex="0" />
      {paginationTag}
      <button className="num_r img_all" onClick={() => currentPageNo < totalPageCount && moveToPage(currentPageNo + 1)} tabIndex="0" />
    </div>
  );
}

export default EgovPaging;