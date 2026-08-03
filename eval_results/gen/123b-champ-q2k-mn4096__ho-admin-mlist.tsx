import { useState, useEffect, useCallback, useRef } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import * as EgovNet from "@/api/egovFetch";
import URL from "@/constants/url";

import EgovLeftNav from "@/components/leftmenu/EgovLeftNavAdmin";
import EgovPaging from "@/components/EgovPaging";

import { itemIdxByPage } from "@/utils/calc";

interface EgovAdminMemberListProps {
  searchCondition?: any;
}

function EgovAdminMemberList(props: EgovAdminMemberListProps) {
  console.group("EgovAdminMemberList");
  console.log("[Start] EgovAdminMemberMemberList ------------------------------");
  console.log("EgovAdminMemberList [props] : ", props);

  const location = useLocation();
  console.log("EgovAdminMemberList [location] : ", location);

  const baseCondition: any = location.state?.searchCondition || {};

  const [searchCondition, setSearchCondition] = useState<any>(() => ({
    pageIndex: 1,
    searchCnd: "0",
    searchWrd: "",
    ...baseCondition,
  }));
  const [paginationInfo, setPaginationInfo] = useState<any>(());

  const cndRef = useRef<HTMLSelectElement | null>(null);
  const wrdRef = useRef<HTMLInputElement | null>(null);

  const [listTag, setListTag] = useState<JSX.Element[]>([]);

  const navigate = useNavigate();

  const handleRowClick = useCallback((item: any) => {
    navigate(URL.ADMIN__MEMBERS__MODIFY, {
      state: {
        uniqId: item.uniqId,
        searchCondition: searchCondition,
      },
    });
  }, [navigate, searchCondition]);

  const retrieveList = useCallback((srchCnd: any) => {
    console.groupCollapsed("EgovAdminMemberList.retrieveList()");
    const retrieveListURL = "/members" + EgovNet.getQueryString(srchCnd);

    const requestOptions: RequestInit = {
      method: "GET",
      headers: {
        "Content-type": "application/json",
      },
    };

    EgovNet.requestFetch(retrieveListURL, requestOptions, (resp) => {
      setPaginationInfo(resp.result.paginationInfo);
      setSearchCondition(srchCnd);

      let mutListTag: JSX.Element[] = [];
      const resultCnt = parseInt(resp.result.paginationInfo.totalRecordCount, 10);
      const currentPageNo = resp.result.paginationInfo.currentPageNo;
      const pageSize = resp.result.paginationInfo.pageSize;

      if (!resp.result.resultList || resp.result.resultList.length === 0) {
        mutListTag.push(
          // 수정] p 태그 대신 tr 태그 사용 (<tbody>)
          (
            (<tr key="0">
              {/* eslint-disable-next-line react/no-unescaped-entities */}
              {<td colSpan={6} className="no__data">검색된 결과가 없습니다.</td>;}
            </tr>) as JSX.Element
          )
        );
      } else {
        resp.result.resultList.forEach((item: any, index: number) => {
          let authNm = "";
          resp.result.groupId__result.forEach((data: any) => {
            if (data.code === item.groupId) authNm = data.codeNm;
          });

          const listIdx = itemIdxByPage(resultCnt, currentPageNo, pageSize, index);

          mutListTag.push((
            (<tr key={listIdx} onClick={() => handleRowClick(item)} >
              {<td>{listIdx}</td>;}
              {<td>{item.mberId}</td>;}
              {<td>{item.mberNm}</td>;}
              {<td>{authNm}</td>;}
              {<td>{item.sbscrbDe}</td>;}
              {<td>{item.mberSttus === "P" ? "가능" : item.mberSttus === "A" ? "대기" : "탈퇴"}</td>;}
            </tr>) as JSX.Element)
          );
        });
      }
      if (!mutListTag.length) {
        mutListTag.push((<p className="no__data" key="0">검색된 결과가 없습니다.</p>) as JSX.Element);
      }
      setListTag(mutListTag);
    }, function (resp: any) {
      console.log("err response : ", resp);
    });
    console.groupEnd("EgovAdminMemberList.retrieveList()");
  }, [setPaginationInfo, setSearchCondition, setListTag, handleRowClick]);

  const handleSearch = () => {
    retrieveList({
      ...searchCondition,
      pageIndex: 1,
      searchCnd: cndRef.current?.value || "",
      searchWrd: wrdRef.current?.value || "",
    });
  };

  useEffect(() => {
    retrieveList(searchCondition);
  }, [searchCondition]);

  console.log("------------------------------EgovAdminMemberList [End]");
  console.groupEnd("EgovAdminMemberList");

  return (
    // JSX code here...
  );
}

export default EgovAdminMemberList;