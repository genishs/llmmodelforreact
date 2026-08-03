import { useState, useEffect } from "react";
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

function EgovAdminMemberList(props) {
  console.group("EgovAdminMemberList");
  console.log("[Start] EgovAdminMemberMemberList ------------------------------");
  console.log("EgovAdminMemberList [props]: ", props);

  const location = useLocation();
  console.log("EgovAdminMemberList [location]: ", location);

  const baseCondition: SearchCondition = {
    pageIndex: 1,
    searchCnd: "0",
    searchWrd: "",
    ...(location.state?.searchCondition || {}), // 기존 조회에서 접근 했을 시 || 신규로 접근 했을 시
  };

  const [searchCondition, setSearchCondition] = useState<SearchCondition>(baseCondition);
  const [paginationInfo, setPaginationInfo] = useState({});

  const cndRef = useRef<HTMLSelectElement | null>(null);
  const wrdRef = useRef<HTMLInputElement | null>(null);

  const [listTag, setListTag] = useState([] as JSX.Element[]);

  const navigate = useNavigate();

  const handleRowClick = (item: any) => {
    //  (item, srtitem) 인자 제거
    navigate(URL.ADMINMEMBERSMODIFY, {
      state: {
        uniqId: item.uniqId,
        searchCondition: searchCondition,
      },
    });
    //  srtitem 인자 사용하지 않으므로 삭제
  };

  const retrieveList = (srchCnd: SearchCondition) => {
    console.groupCollapsed("EgovAdminMemberList.retrieveList()");
    const retrieveListURL = "/members" + EgovNet.getQueryString(srchCnd);

    const requestOptions = {
      method: "GET",
      headers: {
        "Content-type": "application/json",
      },
    };

    EgovNet.requestFetch(retrieveListURL, requestOptions, (resp) => {
      setPaginationInfo(resp.result.paginationInfo);
      setSearchCondition({ ...srchCnd }); //  갱신 전 상태

      let mutListTag = [] as JSX.Element[];
      // listTag.push(
      //   // 수정] p 태그 대신 tr 태그 사용 (tbody 안에 들어가야 함)
      //   // eslint-disable-next-line react/jsx-key
      //   // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-noninteractive-role
      //   // eslint-disable-next-line jsx-a11y/accessible-emoji
      //   // eslint-disable-next-line react/jsx-key
      //   // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-noninteractive-role
      //   // eslint-disable-next-line jsx-a11y/accessible-emoji
      //   // eslint-disable-next-line react/jsx-key
      //   // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-noninteractive-role
      //   // eslint-disable-next-line jsx-a11y/accessible-emoji
      //   // eslint-disable-next-line react/jsx-key
      //   // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-noninteractive-role
      //   // eslint-disable-next-line jsx-a11y/accessible-emoji
      //   // eslint-disable-next-line react/jsx-key
      //   // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-noninteractive-role
      //   // eslint-disable-next-line jsx-a11y/accessible-emoji
      //   // eslint-disable-next-line react/jsx-key
      //   // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-noninteractive-role
      //   // eslint-disable-next-line jsx-a11y/accessible-emoji
      //   // eslint-disable-next-line react/jsx-key
      //   // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-noninteractive-role
      //   // eslint-disable-next-line jsx-a11y/accessible-emoji
      //   // eslint-disable-next-line react/jsx-key
      //   // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-noninteractive-role
      //   // eslint-disable-next-line jsx-a11y/accessible-emoji
      //   // eslint-disable-next-line react/jsx-key
      //   // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-noninteractive-role
      //   // eslint-disable-next-line jsx-a11y/accessible-emoji
      //   // eslint-disable-next-line react/jsx-key
      //   // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-noninteractive-role
      //   // eslint-disable-next-line jsx-a11y/accessible-emoji
      //   // eslint-disable-next-line react/jsx-key
      //   // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-noninteractive-role
      //   // eslint-disable-next-line jsx-a11y/accessible-emoji
      //   // eslint-disable-next-line react/jsx-key
      //   // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-noninteractive-role
      //   // eslint-disable-next-line jsx-a11y/accessible-emoji
      //   // eslint-disable-next-line react/jsx-key
      //   // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-noninteractive-role
      //   // eslint-disable-next-line jsx-a11y/accessible-emoji
      //   // eslint-disable-next-line react/jsx-key
      //   // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-noninteractive-role
      //   // eslint-disable-next-line jsx-a11y/accessible-emoji
      //   // eslint-disable-next-line react/jsx-key
      //   // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-noninteractive-role
      //   // eslint-disable-next-line jsx-a11y/accessible-emoji
      //   // eslint-disable-next-line react/jsx-key
      //   // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-noninteractive-role
      //   // eslint-disable-next-line jsx-a11y/accessible-emoji
      //   // eslint-disable-next-line react/jsx-key
      //   // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-noninteractive-role
      //   // eslint-disable-next-line jsx-a11y/accessible-emoji
      //   // eslint-disable-next-line react/jsx-key
      //   // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-noninteractive-role
      //   // eslint-disable-next-line jsx-a11y/accessible-emoji
      //   // eslint-disable-next-line react/jsx-key
      //   // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-noninteractive-role
      //   // eslint-disable-next-line jsx-a11y/accessible-emoji
      //   // eslint-disable-next-line react/jsx-key
      //   // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-noninteractive-role
      //   // eslint-disable-next-line jsx-a11y/accessible-emoji
      //   // eslint-disable-next-line react/jsx-key
      //   // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-noninteractive-role
      //   // eslint-disable-next-line jsx-a11y/accessible-emoji
      //   // eslint-disable-next-line react/jsx-key
      //   // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-noninteractive-role
      //   // eslint-disable-next-line jsx-a11y/accessible-emoji
      //   // eslint-disable-next-line react/jsx-key
      //   // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-noninteractive-role
      //   // eslint-disable-next-line jsx-a11y/accessible-emoji
      //   // eslint-disable-next-line react/jsx-key
      //   // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-noninteractive-role
      //   // eslint-disable-next-line jsx-a11y/accessible-emoji
      //   // eslint-disable-next-line react/jsx-key
      //   // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-noninteractive-role
      //   // eslint-disable-next-line jsx-a11y/accessible-emoji
      //   // eslint-disable-next-line react/jsx-key
      //   // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-noninteractive-role
      //   // eslint-disable-next-line jsx-a11y/accessible-emoji
      //   // eslint-disable-next-line react/jsx-key
      //   // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-noninteractive-role
      //   // eslint-disable-next-line jsx-a11y/accessible-emoji
      //   // eslint-disable-next-line react/jsx-key
      //   // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-noninteractive-role
      //   // eslint-disable-next-line jsx-a11y/accessible-emoji
      //   // eslint-disable-next-line react/jsx-key
      //   // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-noninteractive-role
      //   // eslint-disable-next-line jsx-a11y/accessible-emoji
      //   // eslint-disable-next-line react/jsx-key
      //   // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-noninteractive-role
      //   // eslint-disable-next-line jsx-a11y/accessible-emoji
      //   // eslint-disable-next-line react/jsx-key
      //   // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-noninteractive-role
      //   // eslint-disable-next-line jsx-a11y/accessible-emoji
      //   // eslint-disable-next-line react/jsx-key
      //   // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-noninteractive-role
      //   // eslint-disable-next-line jsx-a11y/accessible-emoji
      //   // eslint-disable-next-line react/jsx-key
      //   // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-noninteractive-role
      //   // eslint-disable-next-line jsx-a11y/accessible-emoji
      //   // eslint-disable-next-line react/jsx-key
      //   // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-noninteractive-role
      //   // eslint-disable-next-line jsx-a11y/accessible-emoji
      //   // eslint-disable-next-line react/jsx-key
      //   // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-noninteractive-role
      //   // eslint-disable-next-line jsx-a11y/accessible-emoji
      //   // eslint-disable-next-line react/jsx-key
      //   // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-noninteractive-role
      //   // eslint-disable-next-line jsx-a11y/accessible-emoji
      //   // eslint-disable-next-line react/jsx-key
      //   // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-noninteractive-role
      //   // eslint-disable-next-line jsx-a11y/accessible-emoji
      //   // eslint-disable-next-line react/jsx-key
      //   // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-noninteractive-role
      //   // eslint-disable-next-line jsx-a11y/accessible-emoji
      //   // eslint-disable-next-line react/jsx-key
      //   // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-noninteractive-role
      //   // eslint-disable-next-line jsx-a11y/accessible-emoji
      //   // eslint-disable-next-line react/jsx-key
      //   // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-noninteractive-role
      //   // eslint-disable-next-line jsx-a11y/accessible-emoji
      //   // eslint-disable-next-line react/jsx-key
      //   // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-noninteractive-role
      //   // eslint-disable-next-line jsx-a11y/accessible-emoji
      //   // eslint-disable-next-line react/jsx-key
      //   // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to