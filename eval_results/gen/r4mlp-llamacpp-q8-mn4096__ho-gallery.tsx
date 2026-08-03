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
  let filesTag: JSX.Element[] = [];

  if (boardFiles !== undefined) {
    boardFiles.forEach((item, index) => {
      filesTag.push(
        <React.Fragment key={index}>
          <img
            src={`${SERVER_URL}/image?atchFileId=${item.atchFileId}&amp;${item.fileSn}`}
            alt=""
          />
          <br />
        </React.Fragment>
      );
    });
  }

  return <div className="board_attach_img">{filesTag}</div>;
}

export default EgovImageGallery;