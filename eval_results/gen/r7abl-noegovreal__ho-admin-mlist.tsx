import { useState, useEffect, useCallback, useRef } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import * as EgovNet from "@/api/egovFetch";
import URL from "@/constants/url";

import { default as EgovLeftNav } from "@/components/leftmenu/EgovLeftNavAdmin";
import EgovPaging from "@/components/EgovPaging";

interface SearchCondition {
  pageIndex: number;
  searchCnd: string;
  searchWrd: string;
}

interface PaginationInfo {
  totalRecordCount: number;
  currentPageNo: number;
  pageSize: number;
}

function EgovAdminMemberList({}: {}) {
  const location = useLocation<SearchCondition>();
  const [searchCondition, setSearchCondition] = useState<SearchCondition>({
    pageIndex: 1,
    searchCnd: "0",
    searchWrd: "",
    ...location.state?.searchCondition,
  });
  const [paginationInfo, setPaginationInfo] = useState<PaginationInfo>({});
  const cndRef = useRef<HTMLSelectElement>(null);
  const wrdRef = useRef<HTMLInputElement>(null);
  const [listTag, setListTag] = useState<JSX.Element[]>([]);
  const navigate = useNavigate();

  const handleRowClick = useCallback((item: { uniqId: string }) => {
    navigate(URL.ADMIN_MEMBERS_MODIFY, {
      state: { uniqId: item.uniqId, searchCondition },
    });
  }, [navigate, searchCondition]);

  const retrieveList = useCallback(async (srchCnd: SearchCondition) => {
    const retrieveListURL = `/members${EgovNet.getQueryString(srchCnd)}`;
    const requestOptions = { method: "GET", headers: { "Content-type": "application/json" } };
    try {
      const resp = await EgovNet.requestFetch(retrieveListURL, requestOptions);
      setPaginationInfo(resp.result.paginationInfo);
      setSearchCondition(srchCnd);
      const items = resp.result.resultList ?? [];
      setListTag(items.map((item, i) => (
        <tr key={i} onClick={() => handleRowClick(item)} style={{ cursor: "pointer" }}>
          <td>{i + 1}</td>
          <td>{item.mberId}</td>
          <td>{item.mberNm}</td>
          <td>{item.authNm}</td>
          <td>{item.sbscrbDe}</td>
          <td>{["P", "A"].includes(item.mberSttus) ? "가능" : "탈퇴"}</td>
        </tr>
      )));
    } catch (error) { console.error(error); }
  }, [setPaginationInfo, setSearchCondition, setListTag, handleRowClick]);

  const handleSearch = useCallback(() => {
    retrieveList({
      ...searchCondition,
      pageIndex: 1,
      searchCnd: cndRef.current?.value ?? "",
      searchWrd: wrdRef.current?.value ?? "",
    });
  }, [searchCondition, retrieveList]);

  useEffect(() => { retrieveList(searchCondition); }, [searchCondition, retrieveList]);

  return (
    <div id="new_wrap2"><div className="mid_wrap d_flex d_jcc"><div className="w1200">
      <div className="nav_wrap d_flex d_end"><div className="nav d_flex d_end">
        <Link to={URL.MAIN}><div className="nav_ico img_all"></div></Link>
        <div className="nav_ico_arr img_all"></div>
        <Link to={URL.ADMIN}><div className="nav_txt">시스템 운영관리</div></Link>
        <div className="nav_ico_arr img_all"></div>
        <Link><div className="nav_txt">사용자 관리</div></Link>
      </div></div><div><h1 className="txt_cen">사용자 관리</h1>
        <div className="mid_find d_flex d_jcc aic">
          <label className="font20" htmlFor="user_name">검색유형 선택</label>
          <select className="mid_sel" id="user_name" ref={cndRef} onChange={(e) => { cndRef.current!.value = e.target.value; }}><option value="0">사용자 ID</option><option value="1">사용자 명</option></select>
          <label htmlFor="user1" className="font20">검색어</label>
          <input id="user1" type="search" className="w390" placeholder="검색어를 입력하세요" defaultValue={searchCondition.searchWrd} ref={wrdRef} onChange={(e) => { wrdRef.current!.value = e.target.value; }} onKeyDown={(e) => { if (e.key === 'Enter') handleSearch(); }} />
          <Link href="#" to={URL.ADMIN_MEMBERS_CREATE}><div className="blu_btn">등 록</div></Link>
        </div>
      </div>
    </div><div className="bor_wrap d_flex d_jcc"><div className="bor_in1">
      <table className="board"><colgroup><col width="5%" /><col width="15%" /><col width="15%" /><col width="20%" /><col width="20%" /><col width="15%" /></colgroup>
        <tr><th>No</th><th>사용자ID</th><th>사용자 명</th><th>권한 그룹</th><th>생성일</th><th>사용자 상태</th></tr>
        <tbody>{listTag}</tbody>
      </table><div className="num_wrap d_flex d_jcc aic"><EgovPaging pagination={paginationInfo} moveToPage={(page) => retrieveList({ ...searchCondition, pageIndex: page })} /></div>
    </div></div></div></div>
  );
}

export default EgovAdminMemberList;