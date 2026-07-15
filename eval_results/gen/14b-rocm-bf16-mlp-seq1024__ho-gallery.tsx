import React from "react";
import { SERVER_URL } from "@/config";

interface BoardFile {
  atchFileId: string;
  fileSn: number;
}

interface Props {
  boardFiles?: BoardFile[];
}

function EgovImageGallery({ boardFiles }: Props) {
  const [filesTag, setFilesTag] = React.useState<JSX.Element[]>([]);

  React.useEffect(() => {
    if (boardFiles !== undefined) {
      const newFilesTag = boardFiles.map((item, index) => (
        <React.Fragment key={index}>
          <img
            src={`${SERVER_URL}/image?atchFileId=${item.atchFileId}&fileSn=${item.fileSn}`}
            alt=""
          />
          <br />
        </React.Fragment>
      ));
      setFilesTag(newFilesTag);
    }
  }, [boardFiles]);

  console.log("filesTag : ", filesTag);
  console.groupEnd("EgovAttachFile");

  return <div className="board_attach_img">{filesTag}</div>;
}

export default EgovImageGallery;