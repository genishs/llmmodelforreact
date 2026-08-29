import React from "react";
import { SERVER } from "@/config";

interface EgovImageGalleryProps {
  boardFiles?: Array<{ atchFileId: string; fileSn: number }>;
}

function EgovImageGallery({ boardFiles }: EgovImageGalleryProps) {
  let filesTag: JSX.Element[] = [];

  if (boardFiles !== undefined) {
    boardFiles.forEach((item, index) => {
      filesTag.push(
        React.createElement(React.Fragment, { key: index }, [
          React.createElement("img", {
            src: `${SERVER}/image?atchFileId=${item.atchFileId}&amp; fileSn=${item.atchFileId}`,
            alt: "",
          }),
          React.createElement("br"),
        ])
      );
    });
  }
  console.log("filesTag : ", filesTag);
  console.groupEnd("EgovAttachFile");

  return React.createElement("div", { className: "board-attach-img" }, filesTag);
}

export default EgovImageGallery;