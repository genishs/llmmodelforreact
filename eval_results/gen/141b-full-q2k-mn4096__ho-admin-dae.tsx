import { useState, useEffect } from "react";

interface DataAccessDetail {
  id?: string;
  resourceName?: string;
  // Add more properties as needed based on actual data structure
}

function EgovAdminDataAccessEdit(props: any) {
  console.group("EgovAdminDataAccessEdit");
  console.log("[Start] EgovAdminDataAccessEdit ------------------------------");
  console.log("EgovAdminDataAccessEdit [props] : ", props);

  const navigate = useNavigate();
  const location = useLocation();
  const checkRef = useRef<HTMLInputElement[]>([]);

  console.log("EgovAdminDataAccessEdit [location] : ", location);
  const uniqId = location.state?.uniqId || "";
  
  const [modeInfo, setModeInfo] = useState({ mode: props.mode });
  const [detail, setDetail] = useState<DataAccessDetail | null>(null);
  
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
        navigate({ path: URL.ERROR }, { state: { msg: "" } });
    }
    retrieveDetail();
  };

  const retrieveDetail = () => {
    if (modeInfo.mode === CODE.MODE.MODIFY) {
      const retrieveDetailURL = `/dataaccess/update/${uniqId}`;
      const requestOptions = {
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
    let modeStr = modeInfo.mode === CODE.MODE.CREATE ? "POST" : "PUT";
    const requestOptions = {
        method: modeStr,
        headers: {
            "Content-type": "application/json",
        },
        body: JSON.stringify({ ...detail }),
    };

    EgovNet.requestFetch(modeInfo.editURL, requestOptions, (resp) => {
        if (Number(resp.resultCode) === Number(CODE.RCV.SUCCESS)) {
            navigate({ path: URL.ADMIN.DATAACCESS });
        } else {
            navigate(
            { path: URL.ERROR },
            { state: { msg: resp.resultMessage } }
            );
        }
    });
  };

  const deleteBoard = (uniqId: string) => {
    const deleteURL = `/dataaccess/delete/${uniqId}`;

    const requestOptions = {
      method: "DELETE",
      headers: {
        "Content-type": "application/json",
      },
    };

    EgovNet.requestFetch(deleteURL, requestOptions, (resp) => {
      console.log("====>>> board delete= ", resp);
      if (Number(resp.resultCode) === Number(CODE.RCV.SUCCESS)) {
        alert("게시물이 삭제되었습니다.");
        navigate({ path: URL.ADMIN.DATAACCESS }, { replace: true });
      } else {
        alert("ERR : " + resp.resultMessage);
      }
    });
  };

  useEffect(() => {
    initMode();
  }, []);

  return (
    detail && (
      // Dummy Field for DataAccess
      // Add more fields as needed based on actual data structure
      // ...
    )
  );
}

export default EgovAdminDataAccessEdit;