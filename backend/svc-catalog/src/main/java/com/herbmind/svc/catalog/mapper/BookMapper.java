package com.herbmind.svc.catalog.mapper;

import java.util.List;
import java.util.Map;

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

    /**
     * 取某目录节点子树下的全部单元正文，按原书页序排列。
     *
     * <p>三路来源：方剂单元、医案单元（医案本身没有 node_id，靠主治方剂挂到节点上）、
     * 理论单元（第一章那 3 节，ref_type='node'）。
     * 排序用 `meta_jsonb->>'page'` 里的起始页码（形如「第19-22页」取 19），无页码的排最后。
     *
     * <p>三个 id 列表调用方必须保证非空（空列表会生成 `IN ()` 语法错误），服务层用哨兵值兜住。
     *
     * <p>为什么还要按标题兜底：实测 245 个方剂里有 **131 个 `node_id` 为空**（原 ETL 没回填），
     * 只按节点挂接取数会让这些方剂的正文在节/章页上凭空消失。
     * `content_unit.meta_jsonb` 里存了 chapter / section / category 三段名称，
     * 与 book_node.title 是对得上的，所以再用标题匹配一次兜住漏挂的单元。
     * titles 用 chr(1) 拼成一个字符串传进来（避免 MyBatis 反复 foreach），空则传哨兵。
     */
    @Select("<script>"
            + "SELECT u.id AS id, u.ref_type AS ref_type, u.ref_id AS ref_id, u.title AS title,"
            + " u.unit_type AS unit_type, coalesce(u.meta_jsonb->>'page', '') AS page,"
            + " u.content AS content"
            + " FROM content_unit u"
            + " WHERE (u.ref_type = 'formula' AND u.ref_id IN "
            + "<foreach collection='formulaIds' item='x' open='(' separator=',' close=')'>#{x}</foreach>)"
            + " OR (u.ref_type = 'case' AND u.ref_id IN "
            + "<foreach collection='caseIds' item='x' open='(' separator=',' close=')'>#{x}</foreach>)"
            + " OR (u.ref_type = 'node' AND u.ref_id IN "
            + "<foreach collection='nodeIds' item='x' open='(' separator=',' close=')'>#{x}</foreach>)"
            + " OR coalesce(u.meta_jsonb->>'section', '') = ANY(string_to_array(#{titles}, chr(1)))"
            + " OR coalesce(u.meta_jsonb->>'category', '') = ANY(string_to_array(#{titles}, chr(1)))"
            + " OR coalesce(u.meta_jsonb->>'chapter', '') = ANY(string_to_array(#{titles}, chr(1)))"
            + " ORDER BY coalesce(nullif(regexp_replace(coalesce(u.meta_jsonb->>'page', ''),"
            + " '^第([0-9]+).*$', '\\1'), '')::int, 999999), u.id"
            + "</script>")
    List<Map<String, Object>> unitsOfNode(@Param("formulaIds") List<String> formulaIds,
            @Param("caseIds") List<String> caseIds,
            @Param("nodeIds") List<String> nodeIds,
            @Param("titles") String titles);
}
