import { useState, useEffect, useRef } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";

import * as EgovNet from "@/api/egovFetch";
import URL from "@/constants/url";
import CODE from "@/constants/code";

interface Detail {
  id: string;
  resourceName: string;
  // Add other fields based on actual data structure
}

function EgovAdminDataAccessEdit({ mode }: { mode: string }) {
  console.group("EgovAdminDataAccessEdit");
  console.log("[Start] EgovAdminDataAccessEdit ------------------------------");
  console.log("EgovAdminDataAccessEdit [props] : ", { mode });

  const navigate = useNavigate();
  const location = useLocation();
  const checkRef = useRef([]);

  console.log("EgovAdminDataAccessEdit [location] : ", location);
  const uniqId = location.state?.uniqId || "";

  const [detail, setDetail] = useState({} as Detail);

  const initMode = () => {
    switch (mode) {
      case CODE.MODE_CREATE:
        setDetail({});
        break;
      case CODE.MODE_MODIFY:
        retrieveDetail();
        break;
      default:
        navigate({ pathname: URL.ERROR }, { state: { msg: "" } });
    }
  };

  const retrieveDetail = () => {
    if (mode === CODE.MODE_MODIFY) {
      EgovNet.requestFetch(`/dataaccess/update/${uniqId}`, {}, function (resp) {
        setDetail(resp.result.dataAccessVO);
      });
    }
  };

  const updateBoard = () => {
    let url = mode === CODE.MODE_CREATE ? "/dataaccess/insert" : `/dataaccess/update/${uniqId}`;
    EgovNet.requestFetch(url, { method: "POST", body: JSON.stringify(detail) }, (resp) => {
      if (Number(resp.resultCode) === Number(CODE.RCV_SUCCESS)) {
        navigate(URL.ADMIN_DATAACCESS);
      } else {
        navigate({ pathname: URL.ERROR }, { state: { msg: resp.resultMessage } });
      }
    });
  };

  const deleteBoard = () => {
    EgovNet.requestFetch(`/dataaccess/delete/${uniqId}`, { method: "DELETE" }, (resp) => {
      if (Number(resp.resultCode) === Number(CODE.RCV_SUCCESS)) {
        alert("게시물이 삭제되었습니다.");
        navigate(URL.ADMIN_DATAACCESS, { replace: true });
      } else {
        alert("ERR : " + resp.resultMessage);
      }
    });
  };

  useEffect(() => initMode(), [mode]);

  return (
    <div className="container">
      {/* ... */}
    </div>
  );
}

export default EgovAdminDataAccessEdit;