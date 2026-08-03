import { useState, useEffect, useRef } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";

import * as EgovNet from "@/api/egovFetch";
import URL from "@/constants/url";
import CODE from "@/constants/code";

import { default as EgovLeftNav } from "@/components/leftmenu/EgovLeftNavAdmin";
import EgovRadioButtonGroup from "@/components/EgovRadioButtonGroup";

interface EgovAdminDataAccessEditProps {
  mode: string;
}

function EgovAdminDataAccessEdit(props: EgovAdminDataAccessEditProps) {
  console.group("EgovAdminDataAccessEdit");
  console.log("[Start] EgovAdminDataAccessEdit ------------------------------");
  console.log("EgovAdminDataAccessEdit [props] : ", props);

  const navigate = useNavigate();
  const location = useLocation();
  const checkRef = useRef<HTMLDivElement[]>([]);

  console.log("EgovAdminDataAccessEdit [location] : ", location);
  const uniqId: string = location.state?.uniqId || "";

  const [modeInfo, setModeInfo] = useState<{ mode: string; modeTitle?: string; editURL?: string }>(
    { mode: props.mode }
  );
  const [detail, setDetail] = useState<{ id?: string; resourceName?: string; uniqId?: string }>(
    {}
  );

  const initMode = () => {
    switch (props.mode) {
      case CODE.MODE.CREATE:
        setModeInfo({
          ...modeInfo,
          modeTitle: "등록",
          editURL: "/dataaccess/insert",
        });
        break;

      case CODE.MODE.MODIFY:
        setModeInfo({
          ...modeInfo,
          modeTitle: "수정",
          editURL: `/dataaccess/update`,
        });
        break;
      default:
        navigate({ pathName: URL.ERROR }, { state: { msg: "" } });
    }
    retrieveDetail();
  };

  const retrieveDetail = () => {
    if (modeInfo.mode === CODE.MODE.MODIFY) {
      const retrieveDetailURL = `/dataaccess/update/${uniqId}`;
      const requestOptions: RequestInit = {
        method: "GET",
        headers: {
          "Content-type": "application/json",
        },
      };
      EgovNet.requestFetch(retrieveDetailURL, requestOptions, function (resp) {
        setDetail(resp.result.dataAccessVO);
      });
    }
  };

  const updateBoard = () => {
    let modeStr: string = modeInfo.mode === CODE.MODE.CREATE ? "POST" : "PUT";
    const requestOptions: RequestInit = {
        method: modeStr,
        headers: {
            "Content-type": "application/json",
        },
        body: JSON.stringify({ ...detail }),
    };

    EgovNet.requestFetch(modeInfo.editURL!, requestOptions, (resp) => {
        if (Number(resp.resultCode) === Number(CODE.RCV.SUCCESS)) {
            navigate({ pathName: URL.ADMIN.DATAACCESS });
        } else {
            navigate(
            { pathName: URL.ERROR },
            { state: { msg: resp.resultMessage } }
            );
        }
    });
  };

  const deleteBoard = (uniqId: string) => {
    const deleteURL = `/dataaccess/delete/${uniqId}`;

    const requestOptions: RequestInit = {
      method: "DELETE",
      headers: {
        "Content-type": "application/json",
      },
    };

    EgovNet.requestFetch(deleteURL, requestOptions, (resp) => {
      console.log("====>>> board delete= ", resp);
      if (Number(resp.resultCode) === Number(CODE.RCV.SUCCESS)) {
        alert("게시물이 삭제되었습니다.");
        navigate(URL.ADMIN.DATAACCESS, { replace: true });
      } else {
        alert("ERR : " + resp.resultMessage);
      }
    });
  };

  useEffect(() => {
    initMode();
  }, []);

  return (
    // JSX code remains the same as provided
  );
}

export default EgovAdminDataAccessEdit;