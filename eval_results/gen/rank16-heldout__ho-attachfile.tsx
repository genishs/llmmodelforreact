interface Props {
  boardFiles?: any[];
  mode: number;
  fnChangeFile: (arg: FileList | null) => void;
  fnDeleteFile: (arg: any[]) => void;
  posblAtchFileNumber?: number;
}

function EgovAttachFile({ boardFiles, mode, fnChangeFile, fnDeleteFile, posblAtchFileNumber }: Props) {
  console.groupCollapsed("EgovAttachFile");
  if (typeof posblAtchFileNumber == "undefined" || posblAtchFileNumber == null) posblAtchFileNumber = 1;

  const navigate = useNavigate();

  function onClickDownFile(atchFileId: string, fileSn: number) {
    window.open(SERVER_URL + `/file?atchFileId=${atchFileId}&fileSn=${fileSn}`);
  }

  function onClickDeleteFile(atchFileId: string, fileSn: number, fileIndex: number) {
    console.log("onClickDeleteFile Params : ", atchFileId, fileSn, fileIndex);
    const requestOptions = {
      method: "POST",
      headers: { "Content-type": "application/json" },
      body: JSON.stringify({ atchFileId, fileSn }),
    };
    EgovNet.requestFetch("/file", requestOptions, (resp) => {
      console.log("===>>> board file delete= ", resp);
      if (Number(resp.resultCode) === Number(CODE.RCV_SUCCESS)) {
        console.log("Deleted fileIndex = ", fileIndex);
        const _deleteFile = boardFiles?.splice(fileIndex, 1);
        const _boardFiles = Object.assign([], boardFiles);
        fnDeleteFile(_boardFiles);
        alert("첨부파일이 삭제되었습니다.");
        fnChangeFile(null);
      } else {
        navigate({ pathname: URL.ERROR }, { state: { msg: resp.resultMessage } });
      }
    });
  }

  function onChangeFileInput(e: React.ChangeEvent<HTMLInputElement>) {
    console.log("===>>> e = " + e.target.files[0]);
    if (e.target.files.length + (boardFiles?.length || 0) > posblAtchFileNumber) {
      alert(`총 첨부파일 개수는 ${posblAtchFileNumber} 까지 입니다.`);
      e.target.value = "";
      fnChangeFile(null);
      return false;
    }
    fnChangeFile(e.target.files);
  }

  let filesTag: JSX.Element[] = [];
  if (boardFiles) {
    boardFiles.forEach((item, index) => {
      filesTag.push(
        <React.Fragment key={index}>
          <span>
            <a href="#LINK" onClick={(e) => { e.preventDefault(); onClickDownFile(item.atchFileId, item.fileSn); }} download>{item.orignlFileNm}</a>
            <span>[{item.fileMg}byte]</span>
          </span>
        </React.Fragment>
      );
      if (mode === CODE.MODE_MODIFY) {
        filesTag.push(
          <React.Fragment key={[`button`, `${index}`].join("")}>
            <button className="btn btn_delete" onClick={() => onClickDeleteFile(item.atchFileId, item.fileSn, index)}></button>
          </React.Fragment>
        );
      }
      filesTag.push(<br key={[`br`, `${index}`].join("")} />);
    });
  }
  console.log("filesTag : ", filesTag);
  console.groupEnd("EgovAttachFile");

  return (
    <dl>
      <dt>첨부파일</dt>
      <dd>
        <span className="file_attach">
          {filesTag}
          {mode === CODE.MODE_CREATE && (
            <>
              <input name="file_0" id="egovComFileUploader" type="file" multiple onChange={(e) => onChangeFileInput(e)} />
              총 업로드 가능한 첨부파일 개수는 {posblAtchFileNumber} 개 입니다.
            </>
          )}
          {mode === CODE.MODE_MODIFY && filesTag.length / 3 < posblAtchFileNumber && (
            <>
              <input name="file_0" id="egovComFileUploader" type="file" multiple onChange={(e) => onChangeFileInput(e)} />
              현재 업로드 가능한 첨부파일 개수는 {posblAtchFileNumber - filesTag.length / 3} 개 입니다.
            </>
          )}
        </span>
      </dd>
    </dl>
  );
}

export default EgovAttachFile;