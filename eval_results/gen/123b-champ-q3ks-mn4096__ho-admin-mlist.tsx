import { useState, useEffect, useCallback, useRef } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import * as EgovNet from "@/api/egovFetch";
import URL from "@/constants/url";

import { default as EgovLeftNav } from "@/components/leftmenu/EgovLeftNavAdmin";
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
        searchCondition: searchCondition
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

    EgovNet.requestFetch(retrieveListURL, requestOptions, (resp: any) => {
      setPaginationInfo(resp.result.paginationInfo);
      setSearchCondition(srchCnd);

      let mutListTag: JSX.Element[] = [];
      const resultCnt = parseInt(resp.result.paginationInfo.totalRecordCount, 10);
      const currentPageNo = resp.result.paginationInfo.currentPageNo;
      const pageSize = resp.result.paginationInfo.pageSize;

      if (!resp.result.resultList || resp.result.resultList.length === 0) {
        mutListTag.push(
          // 수정] p 태그 대신 tr 태그 사용 (tbody 안에 들어가야 함)
          (<tr key="0">
            {/* eslint-disable-next-line jsx-a11y/role-supports-aria-props */}
            {/* eslint-disable-next-line jsx-a11y/role-has-required-aria-props */}
            {/* eslint-disable-next-line jsx-a11y/no-static-element-interactions */}
            {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-interactive-role */}
            {/* eslint-disable-next-line jsx-a11y/no-static-element-interactions */}
            {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-interactive-role */}
            {/* eslint-disable-next-line jsx-a11y/no-static-element-interactions */}
            {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-interactive-role */}
            {/* eslint-disable-next-line jsx-a11y/no-static-element-interactions */}
            {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-interactive-role */}
            {/* eslint-disable-next-line jsx-a11y/no-static-element-interactions */}
            {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-interactive-role */}
            {/* eslint-disable-next-line jsx-a11y/no-static-element-interactions */}
            {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-interactive-role */}
            {/* eslint-disable-next-line jsx-a11y/no-static-element-interactions */}
            {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-interactive-role */}
            {/* eslint-disable-next-line jsx-a11y/no-static-element-interactions */}
            {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-interactive-role */}
            {/* eslint-disable-next-line jsx-a11y/no-static-element-interactions */}
            {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-interactive-role */}
            {/* eslint-disable-next-line jsx-a11y/no-static-element-interactions */}
            {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-interactive-role */}
            {/* eslint-disable-next-line jsx-a11y/no-static-element-interactions */}
            {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-interactive-role */}
            {/* eslint-disable-next-line jsx-a11y/no-static-element-interactions */}
            {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-interactive-role */}
            {/* eslint-disable-next-line jsx-a11y/no-static-element-interactions */}
            {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-interactive-role */}
            {/* eslint-disable-next-line jsx-a11y/no-static-element-interactions */}
            {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-interactive-role */}
            {/* eslint-disable-next-line jsx-a11y/no-static-element-interactions */}
            {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-interactive-role */}
            {/* eslint-disable-next-line jsx-a11y/no-static-element-interactions */}
            {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-interactive-role */}
            {/* eslint-disable-next-line jsx-a11y/no-static-element-interactions */}
            {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-interactive-role */}
            {/* eslint-disable-next-line jsx-a11y/no-static-element-interactions */}
            {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-interactive-role */}
            {/* eslint-disable-next-line jsx-a11y/no-static-element-interactions */}
            {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-interactive-role */}
            {/* eslint-disable-next-line jsx-a11y/no-static-element-interactions */}
            {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-interactive-role */}
            {/* eslint-disable-next-line jsx-a11y/no-static-element-interactions */}
            {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-interactive-role */}
            {/* eslint-disable-next-line jsx-a11y/no-static-element-interactions */}
            {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-interactive-role */}
            {/* eslint-disable-next-line jsx-a11y/no-static-element-interactions */}
            {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-interactive-role */}
            {/* eslint-disable-next-line jsx-a11y/no-static-element-interactions */}
            {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-interactive-role */}
            {/* eslint-disable-next-line jsx-a11y/no-static-element-interactions */}
            {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-interactive-role */}
            {/* eslint-disable-next-line jsx-a11y/no-static-element-interactions */}
            {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive