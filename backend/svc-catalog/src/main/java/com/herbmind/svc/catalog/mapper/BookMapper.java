package com.herbmind.svc.catalog.mapper;

import java.util.List;

import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.herbmind.svc.catalog.entity.Book;

public interface BookMapper extends BaseMapper<Book> {

    @Select("SELECT count(*) FROM content_unit WHERE book_id = #{bookId}")
    long countUnits(@Param("bookId") String bookId);

    @Select("SELECT count(*) FROM book_node WHERE book_id = #{bookId}")
    long countNodes(@Param("bookId") String bookId);

    @Select("SELECT count(*) FROM formula f JOIN book_node n ON f.node_id = n.id WHERE n.book_id = #{bookId}")
    long countFormulas(@Param("bookId") String bookId);

    @Select("SELECT count(*) FROM case_record c JOIN formula f ON c.main_formula_id = f.id"
            + " JOIN book_node n ON f.node_id = n.id WHERE n.book_id = #{bookId}")
    long countCases(@Param("bookId") String bookId);

    /** 全库统计（首页用）：bookId 传 null 即全库。 */
    @Select("SELECT count(*) FROM formula")
    long countAllFormulas();

    @Select("SELECT count(*) FROM case_record")
    long countAllCases();

    @Select("SELECT count(*) FROM classic_quote")
    long countAllQuotes();

    @Select("SELECT count(*) FROM book_node")
    long countAllNodes();

    @Select("SELECT count(*) FROM content_unit WHERE embedding IS NOT NULL")
    long countAllVectors();

    @Select("SELECT id FROM book ORDER BY id")
    List<String> allBookIds();
}
